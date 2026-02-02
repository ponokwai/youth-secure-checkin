# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Planned Features
- Docker containerization
- Automated tests
- Configuration import/restore functionality
- Event attendance reports
- SMS integration for checkout codes
- Multi-language support

## [1.0.0] - 2025-01-15

### Added
- **Core Check-in System**
  - Family lookup by phone number (last 4 digits)
  - Multi-kid check-in interface
  - Event selection from dropdown
  - Real-time status indicators
  - Check-in/check-out timestamps

- **Security Features**
  - Three-tier authentication (app, admin override, developer)
  - Checkout code system (QR codes + labels)
  - Authorized adults tracking
  - Session encryption
  - Developer password via environment variable

- **Family Management**
  - Add/edit/delete families
  - CSV import with flexible column names
  - CSV export for backup
  - Authorized adults field
  - Notes field for kids (allergies, special needs)

- **Event Management**
  - iCal feed import
  - Manual event creation
  - Configurable date range (±1 to ±12 months)
  - Event history tracking

- **Branding & Customization**
  - Setup wizard for first-time configuration
  - Custom organization name and type
  - Configurable group terminology (Troop, Den, Class, etc.)
  - Color scheme customization (primary, secondary, accent)
  - Logo upload (PNG, JPG, SVG)
  - Favicon support

- **Label Printing**
  - Brother QL series printer support
  - Configurable label text (3 lines)
  - Template placeholders ({family}, {code})
  - QR code and/or label options

- **Backup & Restore**
  - Configuration export (JSON)
  - Configuration import/restore
  - Family data export (CSV)
  - Timestamped backup files

- **Admin Panel**
  - Centralized settings management
  - Security settings (passwords, checkout codes)
  - Branding settings (colors, logo, favicon)
  - Family management interface
  - Event management interface
  - Backup/restore interface

- **User Interface**
  - Responsive Bootstrap 5 design
  - Mobile-friendly check-in
  - Kiosk mode for checkout
  - History view with filtering
  - Dynamic color theming

- **Documentation**
  - Comprehensive README
  - Deployment guide
  - Security best practices
  - FAQ document
  - Complete Wiki guide
  - Export features documentation
  - Contributing guidelines

### Changed
- Renamed project from "troop_checkin" to "youth-secure-checkin"
- Made system organization-agnostic (removed Trail Life hardcoding)
- Split admin settings into Security and Branding pages
- Enhanced CSV import to support multiple column name variations

### Fixed
- Server crashes from missing settings
- Developer password unlock functionality
- Navbar displaying hardcoded organization name
- Database migration issues
- Session handling for override password

### Security
- Passwords hashed in database
- Sensitive settings protected by developer password
- Environment variables for secrets
- Session encryption with SECRET_KEY
- No hardcoded credentials in codebase

## [0.9.0] - 2024-12-01

### Added
- Initial release for Trail Life WI-4603
- Basic check-in/check-out functionality
- QR code checkout
- Family management
- Event import from iCal

### Known Issues
- Hardcoded Trail Life branding
- Limited customization options
- No backup/restore functionality

---

## Version History

- **1.0.0** (2025-01-15) - Public open-source release with full customization
- **0.9.0** (2024-12-01) - Initial Trail Life-specific version

[Unreleased]: https://github.com/ponokwai/youth-secure-checkin/compare/v1.0.0...HEAD
[1.0.0]: https://github.com/ponokwai/youth-secure-checkin/releases/tag/v1.0.0
[0.9.0]: https://github.com/ponokwai/youth-secure-checkin/releases/tag/v0.9.0
