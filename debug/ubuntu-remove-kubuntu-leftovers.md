# Cleaning up KDE / Kubuntu leftovers on Ubuntu

Notes written by GPT 5.6 Sol (attempting --- poorly --- to replicate my voice)


I installed KDE / Kubuntu on my Ubuntu 24.04 machine at some point to try it
out, switched back to Gnome, and thought I had removed it.

Apparently I did not remove all of it.

The thing that made me look into this was screenshots. Previously `PrtSc` would
bring up the normal Gnome screenshot UI where I could drag around a region and
take the screenshot. Now it was opening Spectacle, which had a much larger UI.

I also noticed that the splash screen when restarting the machine still said
Kubuntu.

This machine started as a normal Ubuntu install, so I wanted to figure out what
was still installed from KDE and remove it.

## Initial state

First check what desktop I am actually running:

```bash
echo '=== OS / SESSION ==='
grep -E '^(PRETTY_NAME|ID|VERSION_ID)=' /etc/os-release
echo "XDG_CURRENT_DESKTOP=$XDG_CURRENT_DESKTOP"
echo "DESKTOP_SESSION=$DESKTOP_SESSION"
echo "XDG_SESSION_TYPE=$XDG_SESSION_TYPE"

echo
echo '=== DISPLAY MANAGER ==='
printf '/etc/X11/default-display-manager: '
cat /etc/X11/default-display-manager 2>/dev/null || true
printf 'systemd display-manager.service: '
readlink -f /etc/systemd/system/display-manager.service 2>/dev/null || true
```

On this machine:

```text
PRETTY_NAME="Ubuntu 24.04.4 LTS"
VERSION_ID="24.04"
ID=ubuntu
XDG_CURRENT_DESKTOP=ubuntu:GNOME
DESKTOP_SESSION=ubuntu
XDG_SESSION_TYPE=x11

/etc/X11/default-display-manager: /usr/sbin/gdm3
systemd display-manager.service: /usr/lib/systemd/system/gdm.service
```

So Gnome and GDM are already being used.

Check the screenshot binding:

```bash
gsettings get org.gnome.shell.keybindings show-screenshot-ui
```

gave:

```text
['Print']
```

So Gnome still thinks it owns `PrtSc`.

Check Plymouth:

```bash
readlink -f /usr/share/plymouth/themes/default.plymouth
update-alternatives --query default.plymouth
```

This showed:

```text
/usr/share/plymouth/themes/kubuntu-logo/kubuntu-logo.plymouth
```

and:

```text
Alternative: /usr/share/plymouth/themes/bgrt/bgrt.plymouth
Priority: 110

Alternative: /usr/share/plymouth/themes/kubuntu-logo/kubuntu-logo.plymouth
Priority: 150
```

So that explains the Kubuntu restart splash.

I also checked for KDE things still running:

```bash
systemctl --user --no-pager --type=service --state=running 2>/dev/null \
    | grep -Ei 'kde|plasma|portal' || true
```

This included:

```text
plasma-kactivitymanagerd.service
plasma-kglobalaccel.service
```

which was suspicious given that I was currently in Gnome.

## What KDE packages are still installed?

I used:

```bash
dpkg-query -W -f='${binary:Package} ${db:Status-Status}\n' 2>/dev/null \
    | awk '$2 == "installed" {print $1}' \
    | grep -E '^(kubuntu|kde-|plasma-|sddm|spectacle|xdg-desktop-portal-kde|kubuntu-settings|plymouth-theme-kubuntu|dolphin|konsole|kate|systemsettings|kwin)' \
    | sort || true
```

There was still a lot:

```text
dolphin
dolphin-plugins
kate
...
kde-spectacle
...
kubuntu-desktop
kubuntu-settings-desktop
...
kwin-wayland
kwin-x11
plasma-desktop
plasma-workspace
...
plymouth-theme-kubuntu-logo
plymouth-theme-kubuntu-text
sddm
...
xdg-desktop-portal-kde
```

So KDE definitely wasn't actually gone.

Check which KDE packages apt thinks I explicitly installed:

```bash
apt-mark showmanual \
    | grep -E '^(kubuntu|kde-|plasma-|sddm|spectacle|xdg-desktop-portal-kde|kubuntu-settings|plymouth-theme-kubuntu|dolphin|konsole|kate|systemsettings|kwin)' \
    | sort || true
```

gave:

```text
kubuntu-desktop
plasma-workspace-wayland
```

That sounded right.

I also checked the Ubuntu roots because I did not want to start changing apt
marks just to get through the cleanup:

```bash
apt-mark showmanual \
    | grep -E '^(ubuntu-desktop|ubuntu-desktop-minimal|ubuntu-standard)$' || true

apt-mark showauto \
    | grep -E '^(ubuntu-desktop|ubuntu-desktop-minimal|ubuntu-standard)$' || true
```

The manual packages were already:

```text
ubuntu-desktop
ubuntu-desktop-minimal
ubuntu-standard
```

Good. Leave those alone.

## What did I actually install?

At this point `apt autoremove` wanted to remove a very large list of packages.
Some were obviously KDE packages, but others were things like:

```text
cryptsetup
cryptsetup-initramfs
fonts-ibm-plex
openconnect
ppa-purge
printer-driver-gutenprint
vulkan-tools
```

I did not want to assume all of those were safe just because apt currently
considered them automatic.

Fortunately apt keeps the history:

```bash
for f in /var/log/apt/history.log /var/log/apt/history.log.*.gz; do
    [ -e "$f" ] || continue
    zcat -f "$f"
done | awk '
    BEGIN { RS=""; ORS="\n\n" }
    /kubuntu-desktop|plasma-workspace-wayland/ { print }
'
```

This found:

```text
Start-Date: 2026-04-03  14:58:40
Commandline: apt install kubuntu-desktop
...
End-Date: 2026-04-03  15:00:16

Start-Date: 2026-04-06  11:12:23
Commandline: apt install plasma-workspace-wayland
...
End-Date: 2026-04-06  11:12:24
```

The `kubuntu-desktop` transaction is huge, but importantly it shows which
packages were introduced by that command and which were marked automatic.

The generic-looking packages I was worried about were in that transaction.

So this gives a pretty good record of what happened to the machine when I
installed Kubuntu.

## Start by removing what I explicitly installed

Remove:

```bash
sudo apt purge kubuntu-desktop plasma-workspace-wayland
```

Then inspect the autoremove:

```bash
sudo apt -s autoremove --purge
```

I used `-s` throughout this process before doing any of the larger removals.

After removing those two packages, apt had a large set of KDE packages ready
for autoremove, but some of the core Plasma packages were still keeping each
other installed.

## Remove the remaining Plasma desktop

I checked these:

```bash
for p in \
    plasma-desktop \
    plasma-workspace \
    kwin-x11 \
    sddm \
    xdg-desktop-portal-kde \
    plymouth-theme-kubuntu-logo
do
    echo
    echo "----- $p -----"

    if ! dpkg-query -W -f='${db:Status-Status}\n' "$p" 2>/dev/null \
        | grep -qx installed
    then
        echo "not installed"
        continue
    fi

    if apt-mark showmanual | grep -Fxq "$p"; then
        echo "APT mark: manual"
    else
        echo "APT mark: auto"
    fi

    echo "Installed reverse dependencies:"
    apt-cache rdepends --installed "$p" 2>/dev/null \
        | sed '1,2d' \
        | sed 's/^/  /'
done
```

They were all automatic. There were dependency cycles between the Plasma
packages, which seems to be why they survived the first autoremove.

I simulated:

```bash
sudo apt -s purge \
    plasma-desktop \
    plasma-workspace \
    xdg-desktop-portal-kde \
    plymouth-theme-kubuntu-logo \
    plymouth-theme-kubuntu-text
```

The actual removal list was:

```text
kinfocenter
kubuntu-settings-desktop
plasma-desktop
plasma-widgets-addons
plasma-workspace
plymouth-theme-kubuntu-logo
plymouth-theme-kubuntu-text
sddm-theme-breeze
xdg-desktop-portal-kde
```

No Gnome / Ubuntu desktop packages were in the removal list, so I ran:

```bash
sudo apt purge \
    plasma-desktop \
    plasma-workspace \
    xdg-desktop-portal-kde \
    plymouth-theme-kubuntu-logo \
    plymouth-theme-kubuntu-text
```

and then:

```bash
sudo apt autoremove --purge
```

This removed most of KDE.

## More KDE leftovers, and Kdenlive

After that:

```bash
dpkg-query -W -f='${binary:Package} ${db:Status-Status}\n' 2>/dev/null \
    | awk '$2 == "installed" {print $1}' \
    | grep -E '^(kubuntu|kde-|plasma-|sddm|spectacle|xdg-desktop-portal-kde|kwin)' \
    | sort || true
```

still gave:

```text
kde-cli-tools
kde-cli-tools-data
kde-config-screenlocker
kde-style-breeze
kubuntu-notification-helper
kwin-addons:amd64
kwin-common
kwin-data
kwin-style-breeze
kwin-x11
plasma-framework
```

I tried simulating removal of all of those:

```bash
sudo apt -s purge \
    kde-cli-tools \
    kde-cli-tools-data \
    kde-config-screenlocker \
    kde-style-breeze \
    kubuntu-notification-helper \
    kwin-addons \
    kwin-common \
    kwin-data \
    kwin-style-breeze \
    kwin-x11 \
    plasma-framework
```

But this also wanted to remove:

```text
kdenlive
```

I do want Kdenlive.

Trying again without `plasma-framework` and `kde-style-breeze` still wanted to
remove Kdenlive. It turned out `kwin-style-breeze` was also involved through
the `breeze` dependency.

So I kept the style/framework packages and narrowed the command to:

```bash
sudo apt -s purge \
    kde-cli-tools \
    kde-cli-tools-data \
    kde-config-screenlocker \
    kubuntu-notification-helper \
    kwin-addons \
    kwin-common \
    kwin-data \
    kwin-x11
```

This wanted to remove exactly those eight packages, and Kdenlive was no longer
in the removal list.

Then:

```bash
sudo apt purge \
    kde-cli-tools \
    kde-cli-tools-data \
    kde-config-screenlocker \
    kubuntu-notification-helper \
    kwin-addons \
    kwin-common \
    kwin-data \
    kwin-x11
```

I explicitly installed Kdenlive again:

```bash
sudo apt install kdenlive
```

It was already installed:

```text
kdenlive is already the newest version (4:23.08.5-0ubuntu4).
```

and:

```bash
dpkg-query -W -f='${db:Status-Status} ${binary:Package}\n' \
    kdenlive kdenlive-data 2>/dev/null || true

apt-mark showmanual | grep -x kdenlive || true
```

gave:

```text
installed kdenlive
installed kdenlive-data
kdenlive
```

Then:

```bash
sudo apt -s autoremove --purge
```

had 34 more KDE / Qt packages, but did not include Kdenlive anymore.

So I ran:

```bash
sudo apt autoremove --purge
```

## Final KDE package state

After all of that:

```bash
dpkg-query -W -f='${binary:Package} ${db:Status-Status}\n' 2>/dev/null \
    | awk '$2 == "installed" {print $1}' \
    | grep -E '^(kubuntu|kde-|plasma-|sddm|spectacle|xdg-desktop-portal-kde|kwin)' \
    | sort || true
```

gave:

```text
kde-style-breeze
kwin-style-breeze
plasma-framework
```

I stopped there.

Those are being kept around for applications that use KDE libraries. Trying
to remove some of them is what caused apt to want to remove Kdenlive.

## Plymouth

After removing the Kubuntu Plymouth packages:

```bash
update-alternatives --query default.plymouth
readlink -f /usr/share/plymouth/themes/default.plymouth
```

gave:

```text
Name: default.plymouth
Link: /usr/share/plymouth/themes/default.plymouth
Status: auto
Best: /usr/share/plymouth/themes/bgrt/bgrt.plymouth
Value: /usr/share/plymouth/themes/bgrt/bgrt.plymouth

Alternative: /usr/share/plymouth/themes/bgrt/bgrt.plymouth
Priority: 110
```

and:

```text
/usr/share/plymouth/themes/bgrt/bgrt.plymouth
```

So the Kubuntu Plymouth theme is gone.

I also ran:

```bash
sudo update-initramfs -u
```

because Plymouth is needed during early boot and the theme files get included
in the initramfs.

## Screenshot still did nothing

At this point Spectacle was gone, but pressing `PrtSc` did nothing.

The Gnome binding was still correct:

```bash
gsettings get org.gnome.shell.keybindings show-screenshot-ui
```

```text
['Print']
```

Earlier I had seen these running:

```text
plasma-kactivitymanagerd.service
plasma-kglobalaccel.service
```

This login session had started before I removed KDE, so I tried killing the old
KDE shortcut processes:

```bash
systemctl --user stop \
    plasma-kglobalaccel.service \
    plasma-kactivitymanagerd.service 2>/dev/null || true

pkill -x kglobalaccel5 2>/dev/null || true
pkill -x kactivitymanagerd 2>/dev/null || true

systemctl --user daemon-reload
```

After doing this `PrtSc` immediately worked again and brought up the Gnome
screenshot region tool.

So at least for the screenshot issue, I did not need to reboot.

If that had not worked, because this machine is using X11 I could also have
tried restarting Gnome Shell with:

```text
Alt+F2
r
Enter
```

or just logged out and back in.

## Useful checks

What desktop am I in?

```bash
echo "$XDG_CURRENT_DESKTOP"
echo "$DESKTOP_SESSION"
echo "$XDG_SESSION_TYPE"
```

What display manager am I using?

```bash
cat /etc/X11/default-display-manager
readlink -f /etc/systemd/system/display-manager.service
```

Who has `PrtSc` according to Gnome?

```bash
gsettings get org.gnome.shell.keybindings show-screenshot-ui
```

What Plymouth theme is selected?

```bash
update-alternatives --query default.plymouth
readlink -f /usr/share/plymouth/themes/default.plymouth
```

What KDE desktop-looking packages remain?

```bash
dpkg-query -W -f='${binary:Package} ${db:Status-Status}\n' 2>/dev/null \
    | awk '$2 == "installed" {print $1}' \
    | grep -E '^(kubuntu|kde-|plasma-|sddm|spectacle|xdg-desktop-portal-kde|kwin)' \
    | sort
```

What KDE processes are still running?

```bash
systemctl --user --no-pager --type=service --state=running \
    | grep -Ei 'kde|plasma|kwin|portal'

pgrep -af 'kglobalaccel|kactivity|spectacle|kwin|plasma'
```

Preview autoremove before doing it:

```bash
sudo apt -s autoremove --purge
```

The apt history was particularly useful here:

```text
/var/log/apt/history.log
/var/log/apt/history.log.*.gz
```

because it gave me the actual package set that `apt install kubuntu-desktop`
had added to this machine.

