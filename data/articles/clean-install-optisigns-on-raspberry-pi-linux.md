---
title: Clean install OptiSigns on Raspberry Pi/Linux
article_id: 4411956075027
url: https://support.optisigns.com/hc/en-us/articles/4411956075027-Clean-install-OptiSigns-on-Raspberry-Pi-Linux
updated_at: '2025-08-28T20:09:01Z'
---

Article URL: https://support.optisigns.com/hc/en-us/articles/4411956075027-Clean-install-OptiSigns-on-Raspberry-Pi-Linux

To completely clean out old installation of OptiSigns on Linux or Raspberry Pi

Please run:

```
rm -rf ~/.config/OptiSignsrm ~/.config/autostart/'OptiSigns Digital Signage.desktop'
```

Also delete the long string text on this ~/.config folder

Then install the new AppImage download from <https://www.optisigns.com/download>
