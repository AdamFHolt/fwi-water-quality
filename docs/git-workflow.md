# Git Workflow Guide

## Daily workflow 
```bash
git pull                          # get latest changes before starting
git status                        # see what's changed
git add notebooks/01_clean.py     # stage a specific file
git add .                         # stage everything changed
git commit -m "your message"      # save a snapshot
git push                          # send to GitHub
```

## Setting up on a new machine (first time)

```bash
# 1. Make sure git is installed
git --version

# 2. Install GitHub CLI (if not already)
#    Mac: brew install gh
#    Windows: winget install GitHub.cli

# 3. Log in to GitHub
gh auth login

# 4. Clone the repo
gh repo clone AdamFHolt/fwi-water-quality

# 5. Move into the folder
cd fwi-water-quality
```

After that, the daily workflow above applies.
