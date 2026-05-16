---
name: Bug report
about: Something rendering wrong, crashing, or behaving unexpectedly
title: '[bug] '
labels: bug
assignees: ''
---

**What happened?**
<!-- Briefly describe what you saw vs what you expected. -->

**Render dump**
<!-- Paste the output of this command — it tells me exactly what your terminal is being sent: -->

```
$ python3 ~/.claude/buddy/statusline.py < /dev/null
(paste output here)
```

**Environment**
- Python version: (`python3 --version`)
- OS: (macOS / Linux / WSL)
- Terminal: (iTerm2, Alacritty, kitty, gnome-terminal, etc.)
- Terminal width: (`stty size`)

**Reproduction steps**
1. ...
2. ...

**save.json (optional)**
<!-- If the bug only happens for your specific save, paste the relevant slice
     (REDACT session IDs from watermarks if you care). -->
