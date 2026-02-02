# Contributing to Youth Secure Check-in

Thank you for your interest in contributing to Youth Secure Check-in! This document provides guidelines and instructions for contributing.

## 🌟 Ways to Contribute

### 🐛 Report Bugs
Found a bug? Please [open an issue](../../issues/new) with:
- Clear description of the problem
- Steps to reproduce
- Expected vs actual behavior
- System information (OS, Python version)
- Screenshots if applicable
- Error messages or logs

### 💡 Suggest Features
Have an idea? [Open a discussion](../../discussions/new) or issue with:
- Clear description of the feature
- Use case and benefits
- Potential implementation approach
- Any relevant examples or mockups

### 📝 Improve Documentation
Documentation improvements are always welcome:
- Fix typos or clarify instructions
- Add examples or tutorials
- Translate to other languages
- Improve code comments
- Expand the FAQ or Wiki

### 🔧 Submit Code
Ready to code? Great! See below for development setup.

## 🚀 Development Setup

### Prerequisites
- **Git** - Version control
- **Docker** (recommended) OR Python 3.10+
- **Text editor** - VS Code, PyCharm, etc.
- **Basic Flask knowledge** (helpful but not required)

### Fork and Clone

1. **Fork the repository** on GitHub

2. **Clone your fork**:
   ```bash
   git clone https://github.com/YOUR_USERNAME/youth-secure-checkin.git
   cd youth-secure-checkin
   ```

3. **Add upstream remote**:
   ```bash
   git remote add upstream https://github.com/ponokwai/youth-secure-checkin.git
   ```

### Option 1: Docker Development (Recommended)

**Fast setup with Docker:**

```bash
# Copy environment file
cp .env.docker .env

# Start development environment
docker-compose up -d

# View logs
docker-compose logs -f

# Access at http://localhost:5000
```

**Making code changes:**
- Edit files locally (changes sync automatically via volume mount)
- Restart to apply changes: `docker-compose restart`
- Access shell: `docker-compose exec web /bin/sh`
- View database: `docker-compose exec web sqlite3 data/checkin.db`

**Stop development:**
```bash
docker-compose down
```

### Option 2: Local Python Development

**For Python-native development:**

1. **Create virtual environment**:
   ```bash
   python -m venv venv
   venv\Scripts\activate  # Windows
   # source venv/bin/activate  # Linux/Mac
   ```

2. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

3. **Configure environment**:
   ```bash
   cp .env.example .env
   # Edit .env with your settings
   ```

4. **Initialize and run**:
   ```bash
   python -c "from app import init_db; init_db()"
   python app.py
   # Open http://localhost:5000
   ```

## 📋 Development Guidelines

### Code Style

**Python:**
- Follow PEP 8 style guide
- Use 4 spaces for indentation
- Maximum line length: 100 characters
- Use meaningful variable names
- Add docstrings to functions

**HTML/Templates:**
- Use 2 spaces for indentation
- Keep templates DRY (Don't Repeat Yourself)
- Use semantic HTML5 elements
- Follow Bootstrap 5 conventions

**JavaScript:**
- Use modern ES6+ syntax
- Prefer const/let over var
- Add comments for complex logic
- Keep functions small and focused

### Git Workflow

1. **Create a branch**:
   ```bash
   git checkout -b feature/your-feature-name
   # or
   git checkout -b fix/bug-description
   ```

2. **Make your changes**:
   - Write clear, focused commits
   - Test thoroughly
   - Update documentation if needed

3. **Commit with clear messages**:
   ```bash
   git add .
   git commit -m "Add feature: description of what you added"
   # or
   git commit -m "Fix: description of what you fixed"
   ```

4. **Keep your fork updated**:
   ```bash
   git fetch upstream
   git rebase upstream/master
   ```

5. **Push to your fork**:
   ```bash
   git push origin feature/your-feature-name
   ```

6. **Open Pull Request**:
   - Go to GitHub
   - Click "New Pull Request"
   - Describe your changes
   - Link any related issues

### Commit Message Format

Use clear, descriptive commit messages:

```
Add feature: Brief description of feature

Longer description if needed explaining:
- What was added
- Why it was needed
- Any important details

Fixes #123
```

**Types:**
- `Add feature:` - New functionality
- `Fix:` - Bug fixes
- `Update:` - Updates to existing features
- `Refactor:` - Code improvements without changing functionality
- `Docs:` - Documentation changes
- `Style:` - Formatting, missing semicolons, etc.
- `Test:` - Adding or updating tests
- `Chore:` - Maintenance tasks

### Testing

**Before submitting a PR:**

1. **Manual Testing**:
   - Test the feature/fix thoroughly
   - Try edge cases and boundary conditions
   - Test on different screen sizes (if UI change)
   - Test in both Docker and local environments (if possible)
   - Verify no regressions in existing features

2. **Run Tests** (when available):
   ```bash
   # Local testing
   python -m pytest tests/
   
   # Docker testing
   docker-compose exec web python -m pytest tests/
   ```

3. **Check for Errors**:
   - No Python exceptions or tracebacks
   - No browser console errors (F12 dev tools)
   - No broken links or 404 errors
   - Database operations complete successfully
   - Check Docker logs: `docker-compose logs`

4. **Docker-Specific Testing**:
   ```bash
   # Rebuild to test Dockerfile changes
   docker-compose build --no-cache
   docker-compose up -d
   
   # Verify image size is reasonable
   docker images | grep youth-secure-checkin
   ```

## 🎯 Pull Request Guidelines

### Before Submitting

- [ ] Code follows style guidelines
- [ ] Self-review of code completed
- [ ] Comments added for complex logic
- [ ] Documentation updated (if applicable)
- [ ] No new warnings or errors
- [ ] Tested in local environment
- [ ] Tested in Docker (if making container changes)
- [ ] .dockerignore updated (if adding sensitive files)
- [ ] Commit messages are clear

### PR Description Template

```markdown
## Description
Brief description of the changes

## Type of Change
- [ ] Bug fix
- [ ] New feature
- [ ] Breaking change
- [ ] Documentation update

## Testing
How was this tested?

## Screenshots
If applicable, add screenshots

## Related Issues
Fixes #(issue number)
```

### Review Process

1. **Automated Checks**: 
   - Wait for CI/CD to pass (when implemented)

2. **Code Review**:
   - Maintainer will review your code
   - May request changes
   - Discussion and iteration expected

3. **Approval**:
   - Once approved, PR will be merged
   - You'll be added to contributors list!

## 🐛 Reporting Security Issues

**Do NOT open public issues for security vulnerabilities!**

Instead:
- Use GitHub Security Advisories
- Provide detailed description
- Allow time for patching before disclosure

## 📜 Code of Conduct

### Our Standards

**Positive Behavior:**
- Be respectful and inclusive
- Welcome newcomers
- Give and receive constructive feedback gracefully
- Focus on what's best for the community
- Show empathy towards others

**Unacceptable Behavior:**
- Harassment or discriminatory language
- Trolling or insulting comments
- Personal or political attacks
- Publishing others' private information
- Other unprofessional conduct

### Enforcement

Violations may result in:
1. Warning
2. Temporary ban
3. Permanent ban

Report violations to project maintainers.

## 🏆 Recognition

Contributors are recognized in:
- README contributors section
- Release notes
- GitHub contributors page

## 📞 Questions?

- **General Questions**: [GitHub Discussions](https://github.com/ponokwai/youth-secure-checkin/discussions)
- **Bug Reports**: [GitHub Issues](https://github.com/ponokwai/youth-secure-checkin/issues)
- **Security**: See [SECURITY.md](SECURITY.md)
- **Docker Help**: See [DOCKER.md](DOCKER.md)
- **Deployment**: See [DEPLOYMENT_CHECKLIST.md](DEPLOYMENT_CHECKLIST.md)

## 🎉 Thank You!

Every contribution, no matter how small, helps make this project better for youth organizations everywhere. Thank you for being part of the community!

---

**Happy Contributing! 🚀**
