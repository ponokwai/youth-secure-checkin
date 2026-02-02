# Frequently Asked Questions (FAQ)

## General Questions

### What is Youth Secure Check-in?
Youth Secure Check-in is a free, open-source check-in/check-out system designed for youth organizations. It helps track attendance, manage family records, and ensure children are released only to authorized adults.

### Who is this system designed for?
This system is perfect for:
- Trail Life USA troops and outposts
- Scouting organizations (BSA, Girl Scouts, etc.)
- Churches (children's ministry, youth groups)
- Schools (after-school programs, clubs)
- Community centers (sports teams, activities)
- Childcare facilities
- Any organization tracking youth attendance and pickup

### Is this really free?
Yes! This project is open-source under the MIT License. You can use it, modify it, and deploy it without any licensing fees.

### Do I need programming experience to use this?
No programming experience is required to **use** the system. The setup wizard guides you through initial configuration. However, deploying to a production server does require basic Linux system administration skills. See our [Deployment Guide](../DEPLOYMENT.md) for help.

## Installation & Setup

### What are the system requirements?
**Minimum:**
- Python 3.10 or higher
- 512 MB RAM
- 100 MB disk space
- Modern web browser (Chrome, Firefox, Safari, Edge)

**Recommended:**
- Python 3.11+
- 1 GB RAM
- 500 MB disk space (for logs and backups)
- Linux server for production deployment

### How do I install it?
See the [Quick Start](../README.md#-quick-start) section in the README. Basic steps:
1. Clone the repository
2. Install Python dependencies
3. Configure environment variables
4. Initialize the database
5. Run the application

### What is the `.env` file and why do I need it?
The `.env` file stores sensitive configuration like your secret encryption key and developer password. It should never be committed to Git. Copy `.env.example` to `.env` and fill in your values.

### How do I generate a SECRET_KEY?
Run this Python command:
```bash
python -c "import secrets; print(secrets.token_hex(32))"
```
Copy the output into your `.env` file.

### What should I set as the DEVELOPER_PASSWORD?
Choose a strong, unique password. This is your backup admin access and is required to modify the admin override code. Store it securely (password manager recommended).

### Do I need a domain name?
Not required for local use. For production deployment with external access, a domain name is recommended for SSL/TLS certificates.

## Features & Usage

### How do families check in?
1. Enter last 4 digits of their phone number
2. Select their family from the list
3. Choose the event from the dropdown
4. Tap each child to check them in
5. QR code or label is generated for checkout

### Can multiple families have the same phone number?
The system uses the last 4 digits of phone numbers. If multiple families have the same last 4 digits, they'll both appear in the list. Users select the correct family by name.

### How do checkout codes work?
**QR Codes:**
- Display on screen after check-in
- Scan with any QR code reader
- Opens checkout page automatically

**Printed Labels:**
- Requires Brother QL series printer
- Prints at check-in with family name and code
- Enter code at kiosk to checkout

### Can I use both QR codes and labels?
Yes! In Security Settings, choose "Both Methods" to support families with and without smartphones.

### How do I import families from a CSV?
1. Go to Admin Panel → Families → Import Families
2. Download the CSV template
3. Fill in your family data (see column descriptions)
4. Upload the completed CSV
5. Review the import summary

### What CSV formats are supported?
The import is very flexible and supports multiple column name variations:
- **Phone**: "Mobile Phone", "Phone", "Cell", "Telephone"
- **Group**: Uses your configured term (Troop, Den, Class, Group)
- **Youth**: "Youth", "Y", "Child", "Kid"
- **Authorized Adults**: "Authorized Adults", "Authorized", "Pickup Adults"
- **Notes**: "Notes", "Note", "Comments", "Special Notes"

### How do I backup my data?
**Configuration:**
1. Admin Panel → Backup & Restore → Export
2. Downloads JSON file with all settings

**Family Data:**
1. Admin Panel → Families → Export to CSV
2. Downloads CSV with all family records

### How do I restore from backup?
**Configuration:**
1. Admin Panel → Backup & Restore → Restore
2. Upload your JSON backup file
3. Confirm the restore

**Family Data:**
1. Admin Panel → Families → Import Families
2. Upload your CSV backup

## Security & Access

### What are the different password levels?
1. **App Password**: Main login for check-in/admin access (set in setup wizard)
2. **Admin Override Password**: Allows overriding checkout requirements (set in Security Settings)
3. **Developer Password**: Backup access and unlocks override settings (set in `.env` file)

### I forgot my app password, what do I do?
Use the developer password to log in, then go to Security Settings to reset the app password.

### I forgot my developer password, what do I do?
The developer password is in your `.env` file on the server. If you lost the file:
1. Generate a new developer password
2. Update `.env` with the new password
3. Restart the application

### How secure is this system?
- Passwords are stored with proper hashing
- Session data is encrypted
- No passwords in database (except hashed checkout codes)
- Developer password stored outside database (`.env` only)
- Regular security updates via GitHub

See [SECURITY.md](../SECURITY.md) for detailed security information.

### Can I use this on a public server?
Yes, but ensure you:
- Use HTTPS/SSL (Let's Encrypt recommended)
- Set strong passwords
- Keep the software updated
- Restrict access with firewall rules
- Follow the [Security Guide](../SECURITY.md)

## Customization

### How do I change the organization name and colors?
Admin Panel → Branding Settings. You can customize:
- Organization name and type
- Group terminology (Troop, Den, Class, etc.)
- Primary, secondary, and accent colors
- Logo and favicon

### Can I upload a custom logo?
Yes! Admin Panel → Branding → Upload Logo. Supports PNG, JPG, and SVG. Recommended size: 200x60 pixels.

### How do I change the group term from "Troop" to something else?
Admin Panel → Branding → Group Term. Examples: Den, Class, Patrol, Team, Group, Unit.

### Can I customize the label text?
Yes! Admin Panel → Security → Label Printing Settings. Configure three lines of text with placeholders:
- `{family}` - Family name
- `{code}` - Checkout code

### What events are shown in the dropdown?
Events within your configured date range (set in Branding Settings). Default is ±1 month, adjustable from ±1 to ±12 months.

## Technical Questions

### What database does this use?
SQLite - a lightweight, embedded database. No separate database server needed. The database file is `checkin.db`.

### Can I use PostgreSQL or MySQL?
Currently SQLite only. Database abstraction for other engines is a potential future feature.

### How do I upgrade to a new version?
```bash
cd youth-secure-checkin
git pull
pip install -r requirements.txt --upgrade
# Restart the application
```

### Can I run this in a Docker container?
Docker support is planned for a future release. Current deployment options:
- Linux server with systemd (recommended)
- Heroku/Railway/Render (PaaS)
- Windows/Mac for development only

### What Python version do I need?
Python 3.10 or higher. Python 3.11+ recommended for best performance.

### Does this work on Windows?
Yes for development. For production, Linux is strongly recommended.

## Troubleshooting

### The app won't start - "Module not found" error
Install dependencies: `pip install -r requirements.txt`

### I get "Database is locked" errors
SQLite has limited concurrent write support. This usually means:
- Multiple processes accessing the database
- Restart the application
- Check that only one instance is running

### Labels won't print
1. Check printer is connected and powered on
2. Verify printer model in Security Settings
3. Install Brother QL drivers
4. Test with Brother's software first
5. Check USB permissions (Linux)

### QR codes aren't working
1. Verify the QR code scans to a valid URL
2. Check the code hasn't expired (if using time-based codes)
3. Ensure good lighting for camera scanning
4. Try a different QR scanner app

### Events aren't importing from iCal
1. Verify the iCal URL is accessible
2. Check the URL returns valid iCalendar format
3. Ensure events have start times
4. Check date range settings in Branding

### I can't access the admin panel
1. Log in with app password
2. If forgotten, use developer password
3. If developer password forgotten, check `.env` file

### The system is running slow
1. Check server resources (CPU, RAM, disk)
2. Review database size (`ls -lh checkin.db`)
3. Clear old check-in history if needed
4. Increase worker processes (production)

### Check-ins aren't saving
1. Check disk space
2. Verify database file permissions
3. Check application logs for errors
4. Ensure database isn't corrupted

## Feature Requests & Support

### How do I request a new feature?
Open an issue on [GitHub Issues](https://github.com/ponokwai/youth-secure-checkin/issues) with the "enhancement" label.

### I found a bug, where do I report it?
Open an issue on [GitHub Issues](https://github.com/ponokwai/youth-secure-checkin/issues) with:
- Description of the bug
- Steps to reproduce
- Expected vs actual behavior
- System information (OS, Python version)
- Error messages or logs

### How can I contribute?
See the [Contributing](../README.md#-contributing) section in the README. We welcome:
- Bug fixes
- New features
- Documentation improvements
- Translations
- Testing and feedback

### Is there a user community?
Join the discussion on [GitHub Discussions](https://github.com/ponokwai/youth-secure-checkin/discussions) to:
- Ask questions
- Share tips and tricks
- Show your customizations
- Help other users

### Can I hire someone to set this up for me?
This is an open-source project with no official commercial support. However, you may:
- Post in Discussions to find community members who offer setup services
- Hire a freelance developer or sysadmin
- Contact local tech-savvy volunteers in your organization

## Licensing & Legal

### Can I modify this software?
Yes! The MIT License allows you to:
- Use it commercially
- Modify it
- Distribute it
- Use it privately
- Sublicense it

### Do I need to credit the original author?
The MIT License requires you to include the original license and copyright notice in any copies or substantial portions of the software. Attribution in your documentation is appreciated but not required.

### Can I use this for a paid service?
Yes, the MIT License allows commercial use. However, there's no warranty and you assume all liability.

### Is there a privacy policy?
This software doesn't include a privacy policy. As the operator, you are responsible for:
- Complying with data protection laws (GDPR, COPPA, etc.)
- Creating your own privacy policy
- Obtaining consent to store family data
- Handling data securely

### How is data stored?
All data is stored locally in your SQLite database (`checkin.db`). No data is sent to external servers except:
- iCal event imports (your iCal URL)
- QR code checkout links (if hosted externally)

---

**Still have questions?** Ask on [GitHub Discussions](https://github.com/ponokwai/youth-secure-checkin/discussions)!
