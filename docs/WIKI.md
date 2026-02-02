# Youth Secure Check-in Wiki

Welcome to the Youth Secure Check-in documentation! This wiki provides comprehensive guides for installation, configuration, and usage.

## 📚 Table of Contents

### Getting Started
- [Installation Guide](#installation-guide)
- [First-Time Setup](#first-time-setup)
- [Quick Start Tutorial](#quick-start-tutorial)

### Administration
- [Family Management](#family-management)
- [Event Management](#event-management)
- [Security Settings](#security-settings)
- [Branding Customization](#branding-customization)
- [Backup & Restore](#backup--restore)

### User Guides
- [Check-in Process](#check-in-process)
- [Check-out Process](#check-out-process)
- [Kiosk Mode](#kiosk-mode)
- [History & Reports](#history--reports)

### Advanced Topics
- [Production Deployment](#production-deployment)
- [Label Printer Setup](#label-printer-setup)
- [iCal Integration](#ical-integration)
- [CSV Import/Export](#csv-importexport)
- [Troubleshooting](#troubleshooting)

---

## Installation Guide

### System Requirements

**Minimum Requirements:**
- Operating System: Windows 10+, macOS 10.15+, or Linux (Ubuntu 20.04+)
- Python: 3.10 or higher
- RAM: 512 MB
- Disk Space: 100 MB
- Browser: Chrome 90+, Firefox 88+, Safari 14+, or Edge 90+

**Recommended for Production:**
- Operating System: Ubuntu 22.04 LTS or Debian 11+
- Python: 3.11+
- RAM: 1 GB
- Disk Space: 1 GB
- Nginx or Apache reverse proxy
- SSL/TLS certificate

### Step 1: Install Python

**Windows:**
1. Download Python from [python.org](https://www.python.org/downloads/)
2. Run installer, check "Add Python to PATH"
3. Verify: `python --version`

**macOS:**
```bash
brew install python@3.11
```

**Linux (Ubuntu/Debian):**
```bash
sudo apt update
sudo apt install python3.11 python3.11-venv python3-pip
```

### Step 2: Clone Repository

```bash
# Using HTTPS
git clone https://github.com/ponokwai/youth-secure-checkin.git
cd youth-secure-checkin

# Using SSH (if you have SSH keys configured)
git clone git@github.com:ponokwai/youth-secure-checkin.git
cd youth-secure-checkin
```

### Step 3: Create Virtual Environment

**All Platforms:**
```bash
python -m venv venv
```

**Activate Virtual Environment:**

Windows (PowerShell):
```powershell
venv\Scripts\Activate.ps1
```

Windows (Command Prompt):
```cmd
venv\Scripts\activate.bat
```

macOS/Linux:
```bash
source venv/bin/activate
```

### Step 4: Install Dependencies

```bash
pip install --upgrade pip
pip install -r requirements.txt
```

### Step 5: Configure Environment

```bash
# Copy example environment file
cp .env.example .env
```

Edit `.env` with your preferred text editor:

```ini
# .env
SECRET_KEY=your_generated_secret_key_here
DEVELOPER_PASSWORD=your_secure_developer_password
```

**Generate SECRET_KEY:**
```bash
python -c "import secrets; print(secrets.token_hex(32))"
```

### Step 6: Initialize Database

```bash
python -c "from app import init_db; init_db()"
```

You should see: `Database initialized successfully!`

### Step 7: Run Application

**Development Mode:**
```bash
python app.py
```

**Production Mode** (see [Production Deployment](#production-deployment))

### Step 8: Access Application

Open your browser to:
- Local: `http://localhost:5000`
- Network: `http://YOUR_IP:5000`

You'll be redirected to the setup wizard automatically!

---

## First-Time Setup

### Setup Wizard Overview

The first-time setup wizard guides you through initial configuration in 4 steps.

### Step 1: Organization Details

Configure your organization's information:

**Fields:**
- **Organization Name**: Your organization's full name
  - Example: "Trail Life WI-4603"
  - Example: "First Baptist Church"
  - Example: "Lincoln Elementary School"

- **Organization Type**: Select from dropdown
  - Trail Life USA
  - Scouting Organization
  - Church/Ministry
  - School/Education
  - Community Center
  - Other

- **Group Term**: What you call your groups
  - Troop (default for Trail Life)
  - Den (Cub Scouts)
  - Class (schools, churches)
  - Team (sports)
  - Group (general)
  - Patrol, Unit, etc.

### Step 2: Color Scheme

Choose colors that match your organization's branding:

**Primary Color**: Main buttons and headers
- Default: #79060d (Trail Life red)
- Click color picker to choose custom color

**Secondary Color**: Secondary buttons and accents
- Default: #003b59 (Trail Life blue)

**Accent Color**: Tertiary elements
- Default: #4a582d (Trail Life green)

**Preview**: Colors update in real-time as you select them

### Step 3: Access Code

Set your main login password:

**App Password**: 
- Minimum 4 characters (8+ recommended)
- Used for check-in system and admin panel access
- Store securely - this can be reset later

**Tips:**
- Use a memorable but secure password
- Avoid common words
- Consider a passphrase: "BlueElephant42"
- You can change this anytime in Security Settings

### Step 4: Event Settings

Configure how events appear:

**Event Date Range**: How far back/forward to show events
- ±1 month (recommended for weekly meetings)
- ±2 months
- ±3 months
- ±6 months
- ±12 months (for seasonal organizations)

**Example**: ±1 month shows:
- Events from 1 month ago
- Through 1 month in the future

### Completing Setup

Click "Complete Setup" to:
- Save all configuration
- Create initial database tables
- Generate default settings
- Redirect to check-in page

You can modify all these settings later in the Admin Panel!

---

## Quick Start Tutorial

### Your First Check-in Session

#### Scenario Setup
Let's walk through a typical check-in session:
- Organization: Trail Life Troop
- Event: Weekly Meeting
- Families: Smith family (2 kids), Johnson family (1 kid)

#### Part 1: Add Families

1. **Access Admin Panel**
   - Click top-right profile icon → "Admin Panel"
   - Or navigate to `/admin`

2. **Add Smith Family**
   - Click "Manage Families"
   - Click "Add Family"
   - Phone: 555-1234 (last 4: 1234)
   - Troop: WI-4603
   - Add Adult: "John Smith"
   - Add Kids: "Tommy Smith", "Sarah Smith"
   - Click "Save Family"

3. **Add Johnson Family**
   - Click "Add Family"
   - Phone: 555-5678 (last 4: 5678)
   - Troop: WI-4603
   - Add Adult: "Jane Johnson"
   - Add Kid: "Billy Johnson"
   - Click "Save Family"

#### Part 2: Create Event

1. **Access Events**
   - Admin Panel → "Manage Events"
   - Click "Add Event"

2. **Event Details**
   - Name: "Weekly Meeting"
   - Date: Today's date
   - Time: "19:00" (7:00 PM)
   - Click "Add Event"

#### Part 3: Check-in Families

1. **Return to Check-in**
   - Click "Back to Check-in" or navigate to `/`

2. **Smith Family Check-in**
   - Enter: 1234
   - Click "Smith" family card
   - Select "Weekly Meeting" from dropdown
   - Tap "Tommy Smith" → turns green "Checked In"
   - Tap "Sarah Smith" → turns green "Checked In"
   - QR code displays at top

3. **Johnson Family Check-in**
   - Click "← Back to Search"
   - Enter: 5678
   - Click "Johnson" family card
   - Select "Weekly Meeting"
   - Tap "Billy Johnson" → turns green

#### Part 4: Check-out

1. **Scan QR Code** (with mobile device)
   - Opens checkout page
   - Shows checked-in children
   - Click "Check Out" buttons
   - Confirms checkout

2. **Or Use Kiosk Mode**
   - Navigate to `/kiosk`
   - Enter family code
   - Click "Check Out All"

#### Part 5: View History

1. **Access History**
   - Click "History" in navigation
   - Or navigate to `/history`

2. **Filter Results**
   - Select event from dropdown
   - See all check-in/check-out times
   - Export to CSV if needed

**Congratulations!** You've completed your first check-in session!

---

## Family Management

### Adding Families Manually

#### Single Family Addition

1. Navigate to Admin Panel → Families → Add Family
2. Fill in required fields:
   - **Phone**: Full 10-digit number (stored as last 4)
   - **Troop/Group**: Your group identifier
   - **Authorized Adults**: Comma-separated list (optional)

3. Add family members:
   - **Adults**: Click "Add Adult", enter full name
   - **Kids**: Click "Add Kid", enter name and notes
   - Notes examples: "Allergic to peanuts", "EpiPen in bag"

4. Click "Save Family"

#### Tips for Family Data
- **Phone Numbers**: System uses last 4 digits only
- **Names**: Use full names for clarity
- **Notes**: Include allergies, medical needs, behavioral notes
- **Authorized Adults**: List everyone allowed to pick up

### Editing Families

1. Admin Panel → Families
2. Find family in table
3. Click "Edit" button
4. Modify any field
5. Click "Update Family"

### Deleting Families

**Single Family:**
1. Admin Panel → Families → Edit Family
2. Scroll to bottom
3. Click "Delete Family" (red button)
4. Confirm deletion

**All Families** (use with caution!):
1. Admin Panel → Families
2. Click "Clear All Families" (red button)
3. Confirm deletion
4. ⚠️ This cannot be undone!

### Bulk Import via CSV

See [CSV Import/Export](#csv-importexport) section below.

---

## Event Management

### Manual Event Creation

1. **Access Event Manager**
   - Admin Panel → Events → Add Event

2. **Event Fields**
   - **Name**: Descriptive event name
     - Examples: "Weekly Meeting", "Campout", "Service Project"
   - **Date**: Event date (YYYY-MM-DD)
   - **Time**: Start time (HH:MM in 24-hour format)
     - 19:00 = 7:00 PM
     - 09:30 = 9:30 AM

3. **Click "Add Event"**

### iCal Import

#### Setting Up iCal Feed

**Google Calendar:**
1. Open Google Calendar
2. Click gear icon → Settings
3. Select calendar from left sidebar
4. Scroll to "Integrate calendar"
5. Copy "Secret address in iCal format"

**Outlook/Office 365:**
1. Open Outlook Calendar
2. Settings → View all Outlook settings
3. Calendar → Shared calendars
4. Publish calendar
5. Copy ICS link

**Other Calendar Apps:**
- Look for "Subscribe", "iCal URL", or "Calendar URL" settings
- URL usually ends in `.ics` or `.ical`

#### Importing Events

1. **Admin Panel → Events → Import Events**
2. **Paste iCal URL** into text field
3. **Click "Import Events"**
4. **Review Results**:
   - Shows count of imported events
   - Lists event names and dates
   - Skips duplicates automatically

#### Troubleshooting iCal Import
- **No events imported**: Check URL is publicly accessible
- **Wrong events**: Verify calendar permissions
- **Old events**: Adjust date range in Branding Settings
- **Formatting errors**: Ensure valid iCalendar format

### Editing Events

1. Admin Panel → Events
2. Find event in table
3. Click "Edit"
4. Modify name, date, or time
5. Click "Update Event"

### Deleting Events

**Single Event:**
1. Find event in table
2. Click "Delete" button
3. Confirm deletion

**All Events:**
1. Admin Panel → Events
2. Click "Clear All Events" (use with caution!)
3. Confirm deletion

---

## Security Settings

### Access Passwords

#### App Password
**Purpose**: Main login for check-in and admin access

**Changing App Password:**
1. Admin Panel → Security
2. "Access Codes" section
3. Enter new password (4+ characters)
4. Click "Update Login Code"

#### Admin Override Password
**Purpose**: Override checkout requirements, admin functions

**Changing Override Password:**
1. Admin Panel → Security
2. "Admin Override Code" section
3. Click "Unlock Override Settings"
4. Enter developer password
5. Enter new override password
6. Click "Update Override Code"

**Locking Override Settings:**
- Click "Lock Override Settings" to require developer password again

#### Developer Password
**Purpose**: Backup access, unlock override settings

**Location**: Stored in `.env` file only, never in database

**Changing Developer Password:**
1. Edit `.env` file on server
2. Update `DEVELOPER_PASSWORD=your_new_password`
3. Restart application

### Checkout Code Settings

#### Configuration Options

**Require Checkout Codes:**
- Toggle on/off
- When on: Families must use code to checkout
- When off: Open checkout for anyone

**Checkout Code Method:**
1. **QR Code Only**: Display on screen, scan with phone
2. **Label Only**: Print with Brother QL printer
3. **Both Methods**: Support both options

#### Label Printing Setup

See [Label Printer Setup](#label-printer-setup) section.

**Label Settings:**
- **Line 1**: First line of text
  - Default: "Check-out Code"
- **Line 2**: Second line (supports placeholders)
  - `{family}` = Family name
  - `{code}` = Checkout code
  - Example: "{family}"
- **Line 3**: Third line
  - Example: "{code}"

#### Security Best Practices

1. **Use Strong Passwords**: 8+ characters, mix of types
2. **Change Regularly**: Update passwords quarterly
3. **Limit Access**: Only give passwords to trusted leaders
4. **Enable Checkout Codes**: Prevents unauthorized pickups
5. **Monitor History**: Review check-in/out logs regularly
6. **Backup Often**: Export configuration and family data
7. **Update Software**: Pull latest updates from GitHub

---

## Branding Customization

### Organization Settings

1. **Admin Panel → Branding**
2. **Organization Information**:
   - Name: Update organization name
   - Type: Change organization category
   - Group Term: Modify group terminology

3. **Color Scheme**:
   - Primary: Main buttons and headers
   - Secondary: Secondary elements
   - Accent: Tertiary elements
   - Live preview shows changes

4. **Click "Update Settings"**

### Logo Upload

**Supported Formats**: PNG, JPG, JPEG, SVG

**Recommended Specs:**
- Dimensions: 200x60 pixels (or similar aspect ratio)
- File size: Under 1 MB
- Transparent background (PNG) for best results

**Uploading Logo:**
1. Admin Panel → Branding
2. "Logo" section
3. Click "Choose File"
4. Select your logo image
5. Click "Upload Logo"
6. Logo appears immediately in navigation

**Removing Logo:**
1. Click "Remove Logo" button
2. Reverts to organization name text

### Favicon

**What is a Favicon?**
The small icon that appears in browser tabs and bookmarks.

**Supported Format**: ICO (icon) files

**Creating Favicon:**
- Use online tool: [favicon.io](https://favicon.io)
- Convert PNG to ICO
- Size: 16x16 or 32x32 pixels

**Uploading Favicon:**
1. Admin Panel → Branding
2. "Favicon" section
3. Choose ICO file
4. Upload
5. Refresh browser to see new icon

### Event Date Range

Controls how many months of events appear in dropdown:

**Options:**
- ±1 month: Best for weekly meetings
- ±2 months: Monthly meetings
- ±3 months: Seasonal activities
- ±6 months: Long-term planning
- ±12 months: Annual events

**Changing Date Range:**
1. Admin Panel → Branding
2. "Event Date Range" dropdown
3. Select desired range
4. Click "Update Settings"

---

## Backup & Restore

### Why Backup?

**Protect Against:**
- Accidental data deletion
- Server failures
- Software bugs
- Configuration mistakes
- Hardware issues

**Backup Frequency Recommendations:**
- Configuration: Before any changes
- Family Data: Weekly minimum
- Complete Backup: Monthly

### Configuration Backup

**What's Included:**
- Organization branding
- Colors and styling
- Access codes (app, override, checkout)
- Label printer settings
- Event date range
- All system settings

**What's Excluded:**
- Developer password (stored in `.env`)
- Family data (use separate family export)
- Event data
- Check-in history

#### Exporting Configuration

1. **Admin Panel → Backup & Restore**
2. **Click "Export" (green button)**
3. **File Downloads**: `configuration_backup_YYYYMMDD_HHMMSS.json`
4. **Store Securely**: 
   - Password manager
   - Encrypted USB drive
   - Secure cloud storage
   - Off-site backup

#### Restoring Configuration

1. **Admin Panel → Backup & Restore**
2. **Click "Restore" (orange button)**
3. **Modal Opens with Warnings**:
   - Will overwrite current settings
   - Lists what will be changed
4. **Choose Backup File**
5. **Click "Restore Backup"**
6. **Verify Settings**: Review all settings pages
7. **Restart if Needed**: For certain settings to take effect

### Family Data Backup

**What's Included:**
- All families
- Adults and children
- Phone numbers
- Group assignments
- Authorized adults
- Notes and special information

#### Exporting Families

1. **Admin Panel → Families**
2. **Click "Export to CSV" (green button)**
3. **File Downloads**: `families_export_YYYYMMDD_HHMMSS.csv`
4. **Open in**:
   - Excel
   - Google Sheets
   - LibreOffice Calc
   - Any CSV editor

#### Restoring Families

1. **Admin Panel → Families → Import Families**
2. **Upload CSV File**
3. **Review Import Summary**
4. **Verify in Family List**

### Complete Backup Strategy

**Recommended Process:**

1. **Weekly Routine**:
   ```bash
   # Export both configuration and families
   # Download from Admin Panel or via curl:
   curl -O http://localhost:5000/admin/backup/export
   curl -O http://localhost:5000/admin/families/export
   ```

2. **Store Multiple Versions**:
   - Keep last 4 weeks of backups
   - Label clearly: `backup_2025-01-15.json`

3. **Test Restores**:
   - Quarterly: Restore backup on test instance
   - Verify all data restored correctly

4. **Off-site Storage**:
   - Cloud storage (encrypted)
   - External drive (separate location)
   - USB drive (secure cabinet)

5. **Document Procedure**:
   - Write down backup process
   - Include file locations
   - List recovery steps

---

## Check-in Process

### Standard Check-in Flow

#### Step 1: Login
- Enter app password
- Click "Login"
- Redirected to phone number entry

#### Step 2: Family Lookup
- Enter last 4 digits of phone
- All matching families display
- Click correct family card

#### Step 3: Event Selection
- Dropdown shows events in date range
- Select today's event
- Or choose recent event for late check-in

#### Step 4: Check-in Kids
- All family's children display
- Status indicators:
  - Grey: Not checked in
  - Green: Checked in
  - Red: Checked out
- Tap each child to check in
- Turns green with timestamp

#### Step 5: Checkout Code
- QR code displays at top
- Scan with phone to save code
- Or take photo for later

### Bulk Check-in Tips

**Large Families:**
- Check in all children at once
- Tap rapidly - each tap toggles

**Multiple Families:**
- Use "Back to Search" button
- Enter next family's phone
- Repeat check-in process

**Late Arrivals:**
- Same process works anytime
- Select same event
- Check in additional children

### Check-in for Multiple Events

**Same Day, Multiple Events:**
1. Check in for first event
2. Later, look up family again
3. Select second event
4. Check in again

**Different Checkout Codes:**
- Each event gets unique code
- Keep track of which code for which event

---

## Check-out Process

### QR Code Checkout

#### For Parents (with Smartphone):

1. **At Check-in**: 
   - Scan/photograph QR code displayed
   - Or receive via text (if you've integrated messaging)

2. **At Pickup**:
   - Open QR code on phone
   - Scan with another device, or
   - Tap QR code to open checkout page

3. **Checkout Page**:
   - Shows all checked-in children
   - Tap "Check Out" next to each child
   - Confirms with timestamp

#### For Staff (Scanning QR):

1. Use QR scanner app or built-in camera
2. Scan parent's QR code
3. Opens checkout page automatically
4. Verify parent, allow checkout

### Label Checkout

#### At Check-in:
- Printer outputs label automatically
- Label shows: Family name + checkout code
- Parent keeps label

#### At Pickup:
1. Parent presents label
2. Staff uses Kiosk Mode
3. Enters code from label
4. Shows family's children
5. Click "Check Out" buttons

### Kiosk Mode

**Purpose**: Dedicated checkout station

**Setup:**
1. Open `/kiosk` on tablet or computer
2. Display in pickup area
3. Optionally: Hide navigation (kiosk browser mode)

**Usage:**
1. Parent arrives with code
2. Staff (or parent) enters code
3. Family's checked-in children display
4. Click "Check Out All" or individual buttons
5. Confirmation message

### Manual Override

**When Needed:**
- Lost QR code
- Forgotten checkout code
- Emergency pickup
- Authorized adult not on list

**Process:**
1. Staff opens Admin Panel
2. Navigate to History
3. Find family's check-ins
4. Manually check out children
5. Document reason (notes field)

**Or:**
1. Use admin override password
2. Access checkout without code
3. Verify parent identity
4. Process checkout

---

## Production Deployment

### Overview

Production deployment requires:
- Linux server (Ubuntu recommended)
- Gunicorn WSGI server
- Nginx reverse proxy
- SSL/TLS certificate
- Systemd service

See [DEPLOYMENT.md](../DEPLOYMENT.md) for complete guide.

### Quick Production Setup

```bash
# 1. Update system
sudo apt update && sudo apt upgrade -y

# 2. Install dependencies
sudo apt install python3.11 python3.11-venv nginx

# 3. Create application user
sudo useradd -m -s /bin/bash youthcheckin

# 4. Clone repository
sudo -u youthcheckin git clone https://github.com/ponokwai/youth-secure-checkin.git /home/youthcheckin/app

# 5. Setup application
cd /home/youthcheckin/app
sudo -u youthcheckin python3.11 -m venv venv
sudo -u youthcheckin venv/bin/pip install -r requirements.txt

# 6. Configure environment
sudo -u youthcheckin cp .env.example .env
sudo -u youthcheckin nano .env  # Edit settings

# 7. Initialize database
sudo -u youthcheckin venv/bin/python -c "from app import init_db; init_db()"

# 8. Create systemd service
sudo nano /etc/systemd/system/youth-checkin.service

# 9. Configure Nginx
sudo nano /etc/nginx/sites-available/youth-checkin

# 10. Enable and start
sudo systemctl enable youth-checkin
sudo systemctl start youth-checkin
sudo systemctl enable nginx
sudo systemctl restart nginx
```

### SSL/TLS Setup

**Using Let's Encrypt (Free):**

```bash
# Install Certbot
sudo apt install certbot python3-certbot-nginx

# Get certificate
sudo certbot --nginx -d yourdomain.com

# Auto-renewal
sudo systemctl enable certbot.timer
```

---

## Label Printer Setup

### Supported Printers

**Brother QL Series:**
- QL-500
- QL-570
- QL-700
- QL-800
- QL-820NWB
- Others in QL series

### Hardware Setup

#### Windows:
1. Connect printer via USB
2. Install Brother QL drivers from [brother-usa.com](https://www.brother-usa.com)
3. Test with Brother's P-touch Editor software
4. Note COM port in Device Manager

#### macOS:
1. Connect printer via USB
2. Download Brother QL drivers for Mac
3. Add printer in System Preferences
4. Test print

#### Linux:
1. Connect printer via USB
2. Install CUPS and Brother drivers:
   ```bash
   sudo apt install cups printer-driver-ptouch
   ```
3. Add user to lp group:
   ```bash
   sudo usermod -aG lp $USER
   ```
4. Verify printer:
   ```bash
   lsusb | grep Brother
   ```

### Software Configuration

1. **Admin Panel → Security**
2. **Checkout Code Settings**:
   - Enable "Require Checkout Codes"
   - Select "Label" or "Both Methods"

3. **Label Settings**:
   - Printer Model: Select your QL model
   - Label Size: Usually 62mm x 29mm
   - Line 1: "Check-out Code"
   - Line 2: "{family}"
   - Line 3: "{code}"

4. **Test Print**:
   - Check in a test family
   - Label should print automatically
   - Verify text is readable and centered

### Troubleshooting Labels

**Printer Not Found:**
- Check USB connection
- Verify drivers installed
- Linux: Check USB permissions
- Try different USB port

**Print Quality Issues:**
- Clean print head
- Check label alignment
- Replace label roll if old
- Adjust DPI settings

**Labels Not Printing:**
- Check "Label" is selected in settings
- Verify printer model matches
- Check printer is powered on
- Test with Brother software first

**Text Cut Off:**
- Adjust label size setting
- Use shorter text in Line 1-3
- Check label roll width

---

## iCal Integration

### Calendar Platforms

**Supported:**
- Google Calendar
- Microsoft Outlook
- Apple Calendar (iCloud)
- Any platform with iCal/.ics export

### Getting Your iCal URL

#### Google Calendar:
1. Open [calendar.google.com](https://calendar.google.com)
2. Click gear → Settings
3. Select calendar from sidebar
4. Scroll to "Integrate calendar"
5. Copy "Secret address in iCal format"
   - ⚠️ Never share this public - contains secret key!

#### Microsoft Outlook/Office 365:
1. Open Outlook Calendar
2. Settings → View all Outlook settings
3. Calendar → Shared calendars
4. Select calendar
5. Click "Publish"
6. Copy ICS link

#### Apple iCloud Calendar:
1. Open [icloud.com/calendar](https://icloud.com/calendar)
2. Click share icon next to calendar
3. Check "Public Calendar"
4. Copy webcal:// URL
5. Change `webcal://` to `https://`

### Importing Events

1. **Get iCal URL** (see above)
2. **Admin Panel → Events → Import Events**
3. **Paste URL** in text field
4. **Click "Import Events"**
5. **Review Results**:
   - Count of imported events
   - Event names and dates
   - Any errors or skipped events

### Automatic vs Manual Import

**Current**: Manual import each time

**Future Feature**: Automatic sync

**Workaround**: 
- Schedule weekly imports
- Use cron job to hit import endpoint
- Or import before each meeting

### iCal Best Practices

**For Google Calendar:**
- Create dedicated calendar for meetings/events
- Don't use personal calendar (security)
- Keep calendar public but hard to guess

**Event Details:**
- Use clear, consistent event names
- Include start times
- Recurring events import each instance
- All-day events show with 00:00 time

**Security:**
- iCal URLs contain secret keys
- Don't share URLs publicly
- Regenerate if accidentally exposed
- Use separate calendar for check-in system

---

## CSV Import/Export

### CSV Format Specification

**Required Columns:**
- Last Name
- First Name
- Mobile Phone

**Optional Columns:**
- Youth (Y/blank)
- Address Line 1
- Authorized Adults
- Notes
- Group ID (your group term)

**Column Name Variations** (system auto-detects):
- Phone: "Mobile Phone", "Phone", "Cell", "Telephone"
- Group: Your configured term (Troop, Den, Class, etc.)
- Youth: "Youth", "Y", "Child", "Kid"
- Authorized: "Authorized Adults", "Authorized", "Pickup Adults"
- Notes: "Notes", "Note", "Comments", "Special Notes"

### Export Process

#### Export Families:

1. **Admin Panel → Families**
2. **Click "Export to CSV"**
3. **File Downloads**: `families_export_YYYYMMDD_HHMMSS.csv`
4. **Open in Spreadsheet**:
   - Microsoft Excel
   - Google Sheets
   - LibreOffice Calc
   - Apple Numbers

**CSV Structure:**
```csv
Last Name,First Name,Youth,Mobile Phone,Address Line 1,Authorized Adults,Notes,Group ID
Smith,John,,555-1234,123 Main St,"John Smith, Jane Smith",,WI-4603
Smith,Tommy,Y,555-1234,123 Main St,"John Smith, Jane Smith",Allergic to peanuts,WI-4603
Smith,Sarah,Y,555-1234,123 Main St,"John Smith, Jane Smith",,WI-4603
```

**Notes:**
- One row per person (adults and kids)
- Families grouped by Last Name + Address
- Youth column: Y = kid, blank = adult

### Import Process

#### Prepare CSV:

1. **Download Template**:
   - Admin Panel → Families → Import Families
   - Click "Download CSV Template"

2. **Fill in Data**:
   - One row per person
   - Group family members:
     - Same last name
     - Same phone number
     - Same address
   - Mark youth with "Y"
   - Adults leave Youth column blank

3. **Example Data**:
   ```csv
   Last Name,First Name,Youth,Mobile Phone,Authorized Adults,Notes,Troop
   Johnson,Bob,,555-5678,"Bob Johnson, Mary Johnson",,4603
   Johnson,Billy,Y,555-5678,"Bob Johnson, Mary Johnson",Allergic to bees,4603
   ```

#### Import CSV:

1. **Admin Panel → Families → Import Families**
2. **Choose File**: Select your CSV
3. **Click "Import Families"**
4. **Review Summary**:
   - Count of families imported
   - Count of individuals
   - Any errors or warnings
5. **Verify**: Check Families list

### Common Import Issues

**Phone Numbers:**
- Use full 10-digit number
- System stores last 4 digits only
- Format doesn't matter: "555-1234" or "5551234"

**Family Grouping:**
- Must have identical:
  - Last name
  - Phone number
  - Address
- Different spelling = separate families

**Youth Column:**
- "Y" or "y" = youth/child
- Blank = adult
- Anything else = adult

**Authorized Adults:**
- Comma-separated: "John Smith, Jane Smith"
- Optional field
- Can be same as adults in family

**Notes:**
- Any text
- Useful for: allergies, medical, special needs
- Shows in check-in interface

### Bulk Updates via CSV

**Process:**
1. Export current families
2. Edit in spreadsheet
3. Make changes (add notes, update phones, etc.)
4. Save as CSV
5. Clear all families (backup first!)
6. Import updated CSV

**Warning**: Clear All Families is permanent!

---

## Troubleshooting

### Installation Issues

**"Module not found" Error:**
```bash
# Solution: Install dependencies
pip install -r requirements.txt

# If specific module:
pip install flask  # Replace with missing module
```

**Python Version Error:**
```bash
# Check Python version
python --version  # Must be 3.10+

# Use specific version
python3.11 -m venv venv
```

**Permission Denied (Linux):**
```bash
# Fix ownership
sudo chown -R $USER:$USER /path/to/youth-secure-checkin

# Or run with appropriate user
sudo -u appuser python app.py
```

### Runtime Errors

**Database Locked:**
- Cause: Multiple processes accessing SQLite
- Solution:
  ```bash
  # Find and kill old processes
  ps aux | grep python
  kill <PID>
  
  # Restart application
  python app.py
  ```

**Port Already in Use:**
```bash
# Find process on port 5000
# Linux/Mac:
lsof -i :5000
kill <PID>

# Windows:
netstat -ano | findstr :5000
taskkill /PID <PID> /F
```

**Secret Key Error:**
```bash
# Generate new key
python -c "import secrets; print(secrets.token_hex(32))"

# Add to .env
echo "SECRET_KEY=your_generated_key" >> .env
```

### Application Issues

**Can't Login:**
1. Check password in Security Settings
2. Try developer password from `.env`
3. If locked out:
   ```bash
   # Reset database
   rm checkin.db
   python -c "from app import init_db; init_db()"
   # Run setup wizard again
   ```

**Events Not Showing:**
1. Check event dates vs date range setting
2. Verify events exist (Admin Panel → Events)
3. Adjust date range (Admin Panel → Branding)

**Check-ins Not Saving:**
1. Check disk space: `df -h`
2. Verify database permissions
3. Check logs for errors
4. Try test check-in

**QR Codes Not Working:**
1. Verify QR displays correctly
2. Test with different QR scanner app
3. Check URL in QR code is valid
4. Ensure good lighting for scanning

### Performance Issues

**Slow Loading:**
1. Check server resources: `top` or `htop`
2. Review database size: `ls -lh checkin.db`
3. Clear old check-in history
4. Increase workers (production):
   ```bash
   # Edit systemd service
   ExecStart=.../gunicorn --workers 4 ...
   ```

**High Memory Usage:**
1. Restart application
2. Check for memory leaks in logs
3. Reduce worker count
4. Upgrade server RAM

### Data Issues

**Families Not Showing:**
1. Verify families exist (Admin Panel → Families)
2. Check phone number is correct
3. Try full phone number, not last 4
4. Check no special characters

**Duplicate Families:**
1. Same phone number last 4 digits
2. This is normal - user selects correct one
3. Or use middle name/initial in family name

**Lost Configuration:**
1. Restore from backup
2. Or reconfigure manually
3. Check `.env` file exists

### Getting More Help

**Enable Debug Mode:**
```python
# In app.py, find:
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)  # Set debug=True
```

**Check Logs:**
```bash
# Development:
# Errors show in terminal

# Production (systemd):
sudo journalctl -u youth-checkin -n 100 -f

# Nginx logs:
sudo tail -f /var/log/nginx/error.log
```

**Report Issues:**
- GitHub Issues: Include error messages, steps to reproduce
- Discussions: For questions and general help

---

## Additional Resources

### External Documentation
- [Flask Documentation](https://flask.palletsprojects.com/)
- [Bootstrap 5 Docs](https://getbootstrap.com/docs/5.3/)
- [SQLite Documentation](https://www.sqlite.org/docs.html)

### Community
- [GitHub Discussions](https://github.com/ponokwai/youth-secure-checkin/discussions)
- [Issue Tracker](https://github.com/ponokwai/youth-secure-checkin/issues)
- [FAQ](FAQ.md)

### Contributing
- See [README Contributing Section](../README.md#-contributing)
- Code of Conduct (coming soon)
- Development Setup Guide (coming soon)

---

**Questions?** Open an issue or discussion on GitHub!
