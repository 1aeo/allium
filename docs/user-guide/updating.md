# Updating Allium

This guide covers how to update Allium to the latest version and regenerate your site with fresh data.

---

## 🔄 Two Types of Updates

### 1. Data Updates (Frequent)
Refresh relay data from the Tor network **without** updating Allium code.

**When**: Daily, or as often as needed  
**Purpose**: Get latest relay statistics  
**Time**: ~5 minutes

### 2. Code Updates (Occasional)
Update Allium itself to get new features and bug fixes.

**When**: When new versions are released  
**Purpose**: Get improvements and new features  
**Time**: ~10 minutes

---

## 📊 Updating Data Only

This is the most common operation - refreshing your site with the latest Tor network data.

### Quick Update
```bash
cd allium
python3 allium.py --progress
```

That's it! Your `www/` directory now has fresh data.

### Update to Custom Location
```bash
python3 allium.py --out /var/www/html/tor-metrics --progress
```

### Automated Updates

See **[Configuration Guide](configuration.md#-automated-updates-cron)** for cron setup.

**Quick cron example** (updates every 6 hours):
```bash
# Edit crontab
crontab -e

# Add this line:
0 */6 * * * cd /path/to/allium && python3 allium.py --out /var/www/tor-metrics
```

---

## 🔧 Updating Allium Code

### Step 1: Backup Current Setup

**Backup your output** (if you've made customizations):
```bash
cp -r www/ www-backup/
```

**Note your configuration**:
```bash
# Save your current command
echo "python3 allium.py --out /var/www/tor-metrics --display-bandwidth-units bytes" > my-config.txt
```

### Step 2: Check Current Version

```bash
cd allium
git log --oneline -1
# Shows: commit_hash Short commit message
```

### Step 3: Pull Latest Changes

```bash
# Stash any local changes (if you modified code)
git stash

# Pull latest code
git pull origin master

# Check what changed
git log --oneline -10
```

### Step 4: Update Dependencies

```bash
# Update production dependencies
pip3 install -r config/requirements.txt --upgrade

# Or for development
pip3 install -r config/requirements-dev.txt --upgrade
```

### Step 5: Regenerate Site

```bash
python3 allium.py --progress
```

### Step 6: Verify Output

```bash
# Check that generation succeeded
ls -lh www/index.html

# View locally to verify
cd www && python3 -m http.server 8000
# Visit http://localhost:8000
```

### Step 7: Restore Custom Configurations (if needed)

If you stashed changes:
```bash
git stash pop
```

If you had custom templates:
```bash
# Review and reapply your changes
git diff templates/
```

---

## 🔍 Checking for Updates

### Manual Check

```bash
cd allium
git fetch origin
git status
# Shows: "Your branch is behind 'origin/master' by N commits"
```

### What's New

```bash
# See commits you're missing
git log --oneline HEAD..origin/master

# See detailed changes
git log -p HEAD..origin/master
```

### Release Notes

Check GitHub for release notes:
- Visit: https://github.com/1aeo/allium/releases
- Or check: https://github.com/1aeo/allium/blob/master/CHANGELOG.md (if exists)

---

## 📅 Update Frequency Recommendations

### Data Updates
| Use Case | Frequency | Method |
|----------|-----------|--------|
| **Personal Dashboard** | Every 6-12 hours | Manual or cron |
| **Public Website** | Every 1-6 hours | Cron |
| **Development** | On demand | Manual |
| **Monitoring** | Every 30-60 minutes | Cron |

### Code Updates
| Priority | Frequency | Notes |
|----------|-----------|-------|
| **Security Fixes** | Immediately | Check GitHub security advisories |
| **Feature Updates** | Monthly | Review release notes first |
| **Minor Updates** | Quarterly | When convenient |

---

## 🚨 Troubleshooting Updates

### "Git conflicts after pull"

If you've modified Allium code:
```bash
# See what's conflicting
git status

# Option 1: Keep your changes, discard updates
git checkout --ours path/to/file.py

# Option 2: Take update, discard your changes
git checkout --theirs path/to/file.py

# Option 3: Manually resolve
# Edit the file, remove conflict markers, then:
git add path/to/file.py
git commit
```

### "Dependencies won't install"

```bash
# Upgrade pip first
pip3 install --upgrade pip

# Try again
pip3 install -r config/requirements.txt --upgrade

# If still fails, check Python version
python3 --version  # Need 3.8+
```

### "New version generates different output"

This is normal if:
- New features were added (new pages)
- Calculations were improved (different rankings)
- Bug fixes changed results

**Compare outputs**:
```bash
# Generate to different directory
python3 allium.py --out /tmp/allium-new --progress

# Compare key files
diff www/misc/aroi-leaderboards.html /tmp/allium-new/misc/aroi-leaderboards.html
```

### "Generation fails after update"

```bash
# 1. Check dependencies are installed
pip3 list | grep -i jinja

# 2. Try clean generation
rm -rf www/
python3 allium.py --progress

# 3. Check for error messages
python3 allium.py --progress 2>&1 | tee generation.log

# 4. Report issue on GitHub with generation.log
```

---

## 🔐 Security Updates

### Critical Security Updates

If a security issue is announced:

1. **Update immediately**:
```bash
cd allium
git pull origin master
pip3 install -r config/requirements.txt --upgrade
```

2. **Regenerate site**:
```bash
python3 allium.py --out /var/www/tor-metrics --progress
```

3. **Verify fix**:
```bash
# Check version
git log -1 --oneline

# Run security tests (if in dev mode)
bandit -r .
```

### Dependency Security

Check for vulnerable dependencies:
```bash
# Install safety (if not already)
pip3 install safety

# Check dependencies
safety check -r config/requirements.txt
```

---

## 📦 Update Rollback

If an update causes problems:

### Rollback Code
```bash
# Find previous working commit
git log --oneline -10

# Rollback to specific commit
git checkout <commit-hash>

# Regenerate
python3 allium.py --progress
```

### Restore from Backup
```bash
# If you backed up output
cp -r www-backup/* www/

# If you need to restore code
git reset --hard HEAD~1  # Go back 1 commit
```

---

## 🧪 Testing Updates Before Production

### Test in Staging

```bash
# Generate to test directory
python3 allium.py --out /tmp/allium-test --progress

# Review test output
cd /tmp/allium-test
python3 -m http.server 8001  # Different port
# Visit http://localhost:8001

# If good, deploy to production
python3 allium.py --out /var/www/tor-metrics --progress
```

### Automated Testing

```bash
# Run test suite before deploying
pytest

# Run linters
flake8 allium/

# Run security scan
bandit -r allium/
```

---

## 📋 Update Checklist

Before updating code:
- [ ] Backup current `www/` directory
- [ ] Note current Git commit hash
- [ ] Save cron configuration
- [ ] Document any customizations

After updating code:
- [ ] Check `git log` for changes
- [ ] Update dependencies
- [ ] Regenerate site with `--progress`
- [ ] Verify output locally
- [ ] Check for error messages
- [ ] Redeploy to production
- [ ] Monitor first cron run

---

## 🔗 Update Notifications

### Watch GitHub Repository

1. Visit https://github.com/1aeo/allium
2. Click **Watch** → **Custom** → **Releases**
3. Get email notifications for new releases

### Check for Updates Script

```bash
#!/bin/bash
# save as: check-updates.sh

cd /path/to/allium
git fetch origin
BEHIND=$(git rev-list HEAD..origin/master --count)

if [ "$BEHIND" -gt 0 ]; then
    echo "⚠️ Allium is $BEHIND commits behind"
    echo "Run: git pull origin master"
else
    echo "✅ Allium is up to date"
fi
```

---

## 📚 Related Documentation

- **[Configuration Guide](configuration.md)** - Cron setup and automation
- **[Quick Start](quick-start.md)** - Initial installation
- **[Features Guide](features.md)** - What's in each release
- **[Development Guide](../development/README.md)** - Contributing updates

---

## 💡 Best Practices

✅ **DO**:
- Update data frequently (every 6 hours)
- Test code updates in staging first
- Read release notes before updating
- Keep dependencies current
- Backup before major updates

❌ **DON'T**:
- Auto-update code in production without testing
- Skip reading changelogs
- Ignore security updates
- Update during peak usage
- Forget to backup

---

**Last Updated**: 2025-11-23  
**Applies to**: Allium v2.0+
