#!/usr/bin/env python3
"""
Backup Manager for Youth Secure Check-in
Handles automatic backup rotation with retention policy:
- Keep last 3 backups (recent/daily)
- Keep 1 weekly backup (7+ days old)
- Keep 1 monthly backup (30+ days old)

Supports AES-256 encryption for secure backups containing child information.
"""

import os
import sqlite3
import zipfile
import shutil
from pathlib import Path
from datetime import datetime, timedelta
import tempfile

try:
    import pyzipper
    HAS_PYZIPPER = True
except ImportError:
    pyzipper = None
    HAS_PYZIPPER = False

try:
    import pytz
except ImportError:
    pytz = None


class BackupManager:
    def __init__(self, db_path, backup_dir='data/backups', uploads_dir='uploads', static_uploads_dir='static/uploads', timezone=None, encryption_password=None):
        """
        Initialize backup manager
        
        Args:
            db_path: Path to SQLite database
            backup_dir: Directory to store backups
            uploads_dir: Path to uploads directory (if exists)
            static_uploads_dir: Path to static/uploads directory (if exists)
            timezone: Timezone object (e.g., ZoneInfo or pytz timezone) or None for system local time
            encryption_password: Password for AES-256 encryption (None = no encryption)
        """
        self.db_path = Path(db_path)
        self.backup_dir = Path(backup_dir)
        self.uploads_dir = Path(uploads_dir)
        self.static_uploads_dir = Path(static_uploads_dir)
        self.timezone = timezone
        self.encryption_password = encryption_password
        
        # Create backup directory if it doesn't exist
        self.backup_dir.mkdir(parents=True, exist_ok=True)
    
    def _get_local_now(self):
        """Get current time in configured timezone"""
        if self.timezone:
            return datetime.now(self.timezone)
        return datetime.now()
    
    def set_timezone(self, timezone):
        """Update the timezone used for backup timestamps"""
        self.timezone = timezone
    
    def set_encryption_password(self, password):
        """Update the encryption password for backups"""
        self.encryption_password = password
    
    def is_encryption_available(self):
        """Check if encryption is available (pyzipper installed)"""
        return HAS_PYZIPPER
    
    def is_encryption_enabled(self):
        """Check if encryption is currently enabled"""
        return bool(self.encryption_password and HAS_PYZIPPER)
    
    def create_backup(self, description='Automatic backup'):
        """
        Create a backup zip file with database and uploads
        
        Args:
            description: Optional description for the backup
            
        Returns:
            Path to created backup file
        """
        local_now = self._get_local_now()
        timestamp = local_now.strftime('%Y%m%d_%H%M%S')
        backup_filename = f'backup_{timestamp}.zip'
        backup_path = self.backup_dir / backup_filename
        
        # Determine if we should encrypt
        use_encryption = self.encryption_password and HAS_PYZIPPER
        
        # Create zip file - encrypted or standard
        if use_encryption:
            # Use pyzipper for AES-256 encryption
            with pyzipper.AESZipFile(backup_path, 'w', 
                                     compression=pyzipper.ZIP_DEFLATED,
                                     encryption=pyzipper.WZ_AES) as zf:
                zf.setpassword(self.encryption_password.encode('utf-8'))
                self._add_backup_contents(zf, local_now, description, encrypted=True)
        else:
            # Use standard zipfile (no encryption)
            with zipfile.ZipFile(backup_path, 'w', zipfile.ZIP_DEFLATED) as zf:
                self._add_backup_contents(zf, local_now, description, encrypted=False)
        
        return backup_path
    
    def _add_backup_contents(self, zf, local_now, description, encrypted=False):
        """Add all backup contents to a zip file object"""
        # Add database
        if self.db_path.exists():
            zf.write(self.db_path, arcname='checkin.db')
        
        # Add data directory contents (if any)
        data_dir = self.db_path.parent
        if data_dir.exists() and data_dir.name == 'data':
            for root, dirs, files in os.walk(data_dir):
                # Skip the backups directory itself
                if 'backups' in Path(root).parts:
                    continue
                for file in files:
                    file_path = Path(root) / file
                    arcname = file_path.relative_to(data_dir.parent)
                    zf.write(file_path, arcname=str(arcname))
        
        # Add uploads directory
        if self.uploads_dir.exists():
            for root, dirs, files in os.walk(self.uploads_dir):
                for file in files:
                    file_path = Path(root) / file
                    arcname = file_path.relative_to(self.uploads_dir.parent)
                    zf.write(file_path, arcname=str(arcname))
        
        # Add static/uploads directory
        if self.static_uploads_dir.exists():
            for root, dirs, files in os.walk(self.static_uploads_dir):
                for file in files:
                    file_path = Path(root) / file
                    arcname = file_path.relative_to(self.static_uploads_dir.parent.parent)
                    zf.write(file_path, arcname=str(arcname))
        
        # Add metadata
        metadata = {
            'created_at': local_now.isoformat(),
            'description': description,
            'version': '1.0',
            'timezone': str(self.timezone) if self.timezone else 'system',
            'encrypted': encrypted
        }
        zf.writestr('backup_metadata.txt', str(metadata))
    
    def _is_backup_encrypted(self, backup_path):
        """Check if a backup file is encrypted"""
        try:
            # First try with pyzipper if available (handles AES encrypted files)
            if HAS_PYZIPPER:
                try:
                    with pyzipper.AESZipFile(backup_path, 'r') as zf:
                        # Check if any file in the archive is encrypted
                        for info in zf.infolist():
                            # If file is encrypted, we can't read it without password
                            if info.flag_bits & 0x1:  # Encrypted flag
                                return True
                        # Try to read metadata without password
                        try:
                            metadata_bytes = zf.read('backup_metadata.txt')
                            metadata_str = metadata_bytes.decode('utf-8')
                            if "'encrypted': True" in metadata_str:
                                return True
                        except RuntimeError:
                            # Can't read without password = encrypted
                            return True
                        except:
                            pass
                    return False
                except:
                    pass
            
            # Fall back to standard zipfile
            with zipfile.ZipFile(backup_path, 'r') as zf:
                # Check encryption flag on files
                for info in zf.infolist():
                    if info.flag_bits & 0x1:  # Encrypted flag
                        return True
                # Try to read metadata
                try:
                    metadata_bytes = zf.read('backup_metadata.txt')
                    metadata_str = metadata_bytes.decode('utf-8')
                    if "'encrypted': True" in metadata_str:
                        return True
                except:
                    pass
                return False
        except Exception as e:
            # If we can't open it at all, assume it might be encrypted or corrupted
            return True
    
    def list_backups(self):
        """
        List all available backups with metadata
        
        Returns:
            List of dicts with backup info (filename, size, date, age_days, encrypted)
        """
        backups = []
        local_now = self._get_local_now()
        
        # Get all backup files and sort by modification time (newest first)
        backup_files = list(self.backup_dir.glob('backup_*.zip'))
        backup_files.sort(key=lambda f: f.stat().st_mtime, reverse=True)
        
        for backup_file in backup_files:
            try:
                stat = backup_file.stat()
                # Convert file mtime to timezone-aware datetime if we have a timezone
                if self.timezone:
                    created_time = datetime.fromtimestamp(stat.st_mtime, tz=self.timezone)
                    age_days = (local_now - created_time).days
                else:
                    created_time = datetime.fromtimestamp(stat.st_mtime)
                    age_days = (datetime.now() - created_time).days
                
                # Check if encrypted (with error handling)
                try:
                    is_encrypted = self._is_backup_encrypted(backup_file)
                except:
                    is_encrypted = False  # Default to unencrypted if detection fails
                
                backups.append({
                    'filename': backup_file.name,
                    'path': str(backup_file),
                    'size': stat.st_size,
                    'size_mb': round(stat.st_size / (1024 * 1024), 2),
                    'created': created_time,
                    'created_str': created_time.strftime('%Y-%m-%d %H:%M:%S'),
                    'age_days': age_days,
                    'encrypted': is_encrypted
                })
            except Exception as e:
                # If we can't process this backup, skip it but continue with others
                continue
        
        return backups
    
    def rotate_backups(self):
        """
        Rotate backups according to retention policy:
        - Keep last 3 backups
        - Keep 1 weekly backup (7-30 days old)
        - Keep 1 monthly backup (30+ days old)
        
        Returns:
            Tuple of (kept_count, deleted_count)
        """
        backups = self.list_backups()
        
        if not backups:
            return 0, 0
        
        # Categorize backups
        recent = []      # Last 3 backups
        weekly = []      # 7-30 days old
        monthly = []     # 30+ days old
        
        for backup in backups:
            age = backup['age_days']
            if age < 7:
                recent.append(backup)
            elif age < 30:
                weekly.append(backup)
            else:
                monthly.append(backup)
        
        # Determine which to keep
        to_keep = set()
        
        # Keep last 3 recent backups
        for backup in recent[:3]:
            to_keep.add(backup['filename'])
        
        # Keep 1 weekly backup (oldest in weekly range)
        if weekly:
            to_keep.add(weekly[-1]['filename'])
        
        # Keep 1 monthly backup (oldest available)
        if monthly:
            to_keep.add(monthly[-1]['filename'])
        
        # Delete backups not in keep list
        deleted_count = 0
        for backup in backups:
            if backup['filename'] not in to_keep:
                Path(backup['path']).unlink()
                deleted_count += 1
        
        kept_count = len(to_keep)
        return kept_count, deleted_count
    
    def restore_backup(self, backup_filename, password=None):
        """
        Restore from a backup file
        
        Args:
            backup_filename: Name of backup file to restore
            password: Password for encrypted backups (uses instance password if not provided)
            
        Returns:
            Tuple of (success, message)
        """
        backup_path = self.backup_dir / backup_filename
        
        if not backup_path.exists():
            return False, f"Backup file not found: {backup_filename}"
        
        # Use provided password or fall back to instance encryption password
        restore_password = password or self.encryption_password
        
        try:
            # Create temporary directory for extraction
            with tempfile.TemporaryDirectory() as tmpdir:
                # Try to extract - first check if encrypted
                extracted = False
                
                # Try with pyzipper (handles both encrypted and unencrypted)
                if HAS_PYZIPPER:
                    try:
                        with pyzipper.AESZipFile(backup_path, 'r') as zf:
                            if restore_password:
                                zf.setpassword(restore_password.encode('utf-8'))
                            zf.extractall(tmpdir)
                            extracted = True
                    except (RuntimeError, pyzipper.BadZipFile) as e:
                        if 'password' in str(e).lower() or 'encrypted' in str(e).lower():
                            return False, "Backup is encrypted. Please provide the correct password."
                        # Not an encryption error, try standard zipfile
                        pass
                
                # Fall back to standard zipfile for unencrypted backups
                if not extracted:
                    try:
                        with zipfile.ZipFile(backup_path, 'r') as zf:
                            zf.extractall(tmpdir)
                            extracted = True
                    except RuntimeError as e:
                        if 'password' in str(e).lower() or 'encrypted' in str(e).lower():
                            return False, "Backup is encrypted but pyzipper is not installed. Cannot restore."
                        raise
                
                tmpdir_path = Path(tmpdir)
                
                # Backup current database before restoring
                if self.db_path.exists():
                    backup_current = self.db_path.parent / f'checkin_before_restore_{datetime.now().strftime("%Y%m%d_%H%M%S")}.db'
                    shutil.copy2(self.db_path, backup_current)
                
                # Restore database
                db_backup = tmpdir_path / 'checkin.db'
                if db_backup.exists():
                    shutil.copy2(db_backup, self.db_path)
                
                # Restore data directory
                data_backup = tmpdir_path / 'data'
                if data_backup.exists():
                    data_dir = self.db_path.parent
                    for item in data_backup.iterdir():
                        if item.name == 'backups':
                            continue  # Don't restore old backups
                        dest = data_dir / item.name
                        if item.is_file():
                            shutil.copy2(item, dest)
                        elif item.is_dir():
                            if dest.exists():
                                shutil.rmtree(dest)
                            shutil.copytree(item, dest)
                
                # Restore uploads
                uploads_backup = tmpdir_path / 'uploads'
                if uploads_backup.exists():
                    if self.uploads_dir.exists():
                        shutil.rmtree(self.uploads_dir)
                    shutil.copytree(uploads_backup, self.uploads_dir)
                
                # Restore static/uploads
                static_uploads_backup = tmpdir_path / 'static' / 'uploads'
                if static_uploads_backup.exists():
                    if self.static_uploads_dir.exists():
                        shutil.rmtree(self.static_uploads_dir)
                    shutil.copytree(static_uploads_backup, self.static_uploads_dir)
            
            return True, f"Successfully restored from {backup_filename}"
        
        except Exception as e:
            return False, f"Restore failed: {str(e)}"
    
    def delete_backup(self, backup_filename):
        """
        Delete a specific backup file
        
        Args:
            backup_filename: Name of backup file to delete
            
        Returns:
            Tuple of (success, message)
        """
        backup_path = self.backup_dir / backup_filename
        
        if not backup_path.exists():
            return False, f"Backup file not found: {backup_filename}"
        
        try:
            backup_path.unlink()
            return True, f"Deleted backup: {backup_filename}"
        except Exception as e:
            return False, f"Delete failed: {str(e)}"
    
    def get_backup_summary(self):
        """
        Get summary of backup status
        
        Returns:
            Dict with backup statistics
        """
        backups = self.list_backups()
        
        if not backups:
            return {
                'total_backups': 0,
                'total_size_mb': 0,
                'newest_backup': None,
                'oldest_backup': None
            }
        
        total_size = sum(b['size'] for b in backups)
        
        return {
            'total_backups': len(backups),
            'total_size_mb': round(total_size / (1024 * 1024), 2),
            'newest_backup': backups[0],
            'oldest_backup': backups[-1]
        }


def main():
    """Test backup manager"""
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python backup_manager.py <command>")
        print("Commands: create, list, rotate, summary")
        sys.exit(1)
    
    db_path = os.getenv('DATABASE_PATH', 'data/checkin.db')
    manager = BackupManager(db_path)
    
    command = sys.argv[1]
    
    if command == 'create':
        backup_path = manager.create_backup('Manual backup')
        print(f"Created backup: {backup_path}")
    
    elif command == 'list':
        backups = manager.list_backups()
        print(f"\nFound {len(backups)} backups:")
        for b in backups:
            print(f"  {b['filename']} - {b['size_mb']}MB - {b['created_str']} ({b['age_days']} days old)")
    
    elif command == 'rotate':
        kept, deleted = manager.rotate_backups()
        print(f"Rotation complete: kept {kept}, deleted {deleted}")
    
    elif command == 'summary':
        summary = manager.get_backup_summary()
        print("\nBackup Summary:")
        print(f"  Total backups: {summary['total_backups']}")
        print(f"  Total size: {summary['total_size_mb']}MB")
        if summary['newest_backup']:
            print(f"  Newest: {summary['newest_backup']['created_str']}")
            print(f"  Oldest: {summary['oldest_backup']['created_str']}")
    
    else:
        print(f"Unknown command: {command}")
        sys.exit(1)


if __name__ == '__main__':
    main()
