#!/bin/bash

#set -x  # command tracing
set -o errexit
set -o nounset


PATH=/bin:/usr/bin
export PATH


HOTSPOT_DEV="wlan0"
HOTSPOT_IP="10.42.0.1"
HOTSPOT_SSID="IndiAllsky"
HOTSPOT_PSK="indiallsky"

### Use this if you have multiple cameras
#HOTSPOT_SSID="IndiAllsky${RANDOM}"


HOTSPOT_BANDS="bg a"

# Not sure of the possible channel combinations, may need more 5Ghz channels for countries outside US
HOTSPOT_CHANNELS="1 2 3 4 5 6 7 8 9 10 11 12 13 14 36 40 44 48"


DISTRO_NAME=$(lsb_release -s -i)
DISTRO_RELEASE=$(lsb_release -s -r)
CPU_ARCH=$(uname -m)


echo
echo "#######################################################"
echo "### Welcome to the indi-allsky hotspot setup script ###"
echo "#######################################################"

if [[ "$(id -u)" == "0" ]]; then
    echo "Please do not run this script as root"
    echo "Re-run this script as the user which will execute the indi-allsky software"
    echo
    echo
    exit 1
fi


if [[ -f "/etc/astroberry.version" ]]; then
    echo "Please do not run this script on an Astroberry server"
    echo "Astroberry has native hotspot support"
    echo
    echo
    exit 1
fi


echo
echo
echo "This script sets up a wifi hotspot for your Allsky camera"
echo
echo
echo "Distribution: $DISTRO_NAME"
echo "Release: $DISTRO_RELEASE"
echo "Arch: $CPU_ARCH"
echo
echo
echo "SSID: $HOTSPOT_SSID"
echo "PSK:  $HOTSPOT_PSK"
echo "IP:   $HOTSPOT_IP"
echo
echo


echo "Setup proceeding in 10 seconds... (control-c to cancel)"
echo
sleep 10


# Run sudo to ask for initial password
sudo true


echo "**** Installing packages... ****"
if [[ "$DISTRO_NAME" == "Raspbian" && "$DISTRO_RELEASE" == "11" ]]; then

    sudo apt-get update
    sudo apt-get -y install \
        network-manager \
        tzdata

elif [[ "$DISTRO_NAME" == "Raspbian" && "$DISTRO_RELEASE" == "10" ]]; then

    sudo apt-get update
    sudo apt-get -y install \
        network-manager \
        tzdata

elif [[ "$DISTRO_NAME" == "Debian" && "$DISTRO_RELEASE" == "11" ]]; then

    sudo apt-get update
    sudo apt-get -y install \
        network-manager \
        tzdata

elif [[ "$DISTRO_NAME" == "Debian" && "$DISTRO_RELEASE" == "10" ]]; then

    sudo apt-get update
    sudo apt-get -y install \
        network-manager \
        tzdata

elif [[ "$DISTRO_NAME" == "Ubuntu" && "$DISTRO_RELEASE" == "22.04" ]]; then

    sudo apt-get update
    sudo apt-get -y install \
        network-manager \
        tzdata

elif [[ "$DISTRO_NAME" == "Ubuntu" && "$DISTRO_RELEASE" == "20.04" ]]; then

    sudo apt-get update
    sudo apt-get -y install \
        network-manager \
        tzdata

else
    echo "Unknown distribution $DISTRO_NAME $DISTRO_RELEASE ($CPU_ARCH)"
    exit 1
fi


# find script directory for service setup
SCRIPT_DIR=$(dirname "$0")
cd "$SCRIPT_DIR/.."
ALLSKY_DIRECTORY=$PWD
cd "$OLDPWD"


echo "*** Setup wifi for specific country ***"
#COUNTRIES=$(grep -v "^#" /usr/share/zoneinfo/iso3166.tab | sed -e "s/[\t\ ]/_/g")
COUNTRIES=$(grep -v "^#" /usr/share/zoneinfo/iso3166.tab | awk "{print \$1}")
PS3="Please select your country for proper wifi channel selection: "
select code_country in $COUNTRIES; do
    if [[ -n "$code_country" ]]; then
        #COUNTRY_CODE=$(echo $code_country | awk -F_ "{print \$1}")
        COUNTRY_CODE=$code_country
        break
    fi
done

echo "You selected country $COUNTRY_CODE"
sleep 3

echo "options cfg80211 ieee80211_regdom=${COUNTRY_CODE}" | sudo tee /etc/modprobe.d/cfg80211.conf
sudo chown root:root /etc/modprobe.d/cfg80211.conf
sudo chmod 644 /etc/modprobe.d/cfg80211.conf



echo "*** Setup wifi band ***"
PS3="Please select a wifi band: "
select wifi_band in $HOTSPOT_BANDS; do
    if [[ -n "$wifi_band" ]]; then
        HOTSPOT_BAND=$wifi_band
        break
    fi
done

echo "You selected band $HOTSPOT_BAND"
sleep 3


echo "*** Setup wifi channel ***"
PS3="Please select a wifi channel: "
select wifi_channel in $HOTSPOT_CHANNELS; do
    if [[ -n "$wifi_channel" ]]; then
        if [[ "$HOTSPOT_BAND" == "bg" && "$wifi_channel" -le 14 ]]; then
            HOTSPOT_CHANNEL=$wifi_channel
            break
        elif [[ "$HOTSPOT_BAND" == "a" && "$wifi_channel" -gt 14 ]]; then
            HOTSPOT_CHANNEL=$wifi_channel
            break
        else
            echo "Invalid channel for band"
        fi
    fi
done

echo "You selected channel $HOTSPOT_CHANNEL"
sleep 3


echo "**** Setup policy kit permissions ****"
TMP8=$(mktemp)
sed \
 -e "s|%ALLSKY_USER%|$USER|g" \
 "${ALLSKY_DIRECTORY}/service/90-org.aaronwmorris.indi-allsky.pkla" > "$TMP8"

sudo cp -f "$TMP8" "/etc/polkit-1/localauthority/50-local.d/90-org.aaronwmorris.indi-allsky.pkla"
sudo chown root:root "/etc/polkit-1/localauthority/50-local.d/90-org.aaronwmorris.indi-allsky.pkla"
sudo chmod 644 "/etc/polkit-1/localauthority/50-local.d/90-org.aaronwmorris.indi-allsky.pkla"
[[ -f "$TMP8" ]] && rm -f "$TMP8"



if [[ -f "/etc/dhcpcd.conf" ]]; then
    if ! grep -q -e "^denyinterfaces $HOTSPOT_DEV" /etc/dhcpcd.conf; then
        echo "denyinterfaces $HOTSPOT_DEV" | sudo tee -a /etc/dhcpcd.conf
        sudo systemctl daemon-reload
        sudo systemctl restart dhcpcd
    fi
fi


sudo rfkill unblock wlan
sudo nmcli radio wifi on

sudo nmcli connection del HotSpot || true

sleep 5

sudo nmcli connection add \
    ifname "$HOTSPOT_DEV" \
    type wifi \
    con-name "HotSpot" \
    autoconnect no \
    wifi.mode ap \
    wifi.ssid "$HOTSPOT_SSID" \
    802-11-wireless.powersave 2 \
    802-11-wireless.band "$HOTSPOT_BAND" \
    802-11-wireless.channel "$HOTSPOT_CHANNEL" \
    ip4 "${HOTSPOT_IP}/24" \
    ipv6.method auto


sudo nmcli connection modify HotSpot \
    wifi-sec.key-mgmt wpa-psk

sudo nmcli connection modify HotSpot \
    wifi-sec.psk "$HOTSPOT_PSK"

# force WPA2 (rsn) and AES (ccmp)
sudo nmcli connection modify HotSpot \
    802-11-wireless-security.proto rsn \
    802-11-wireless-security.group ccmp \
    802-11-wireless-security.pairwise ccmp

sudo nmcli connection modify HotSpot \
    autoconnect yes


sudo nmcli connection down HotSpot || true
sleep 3
sudo nmcli connection up HotSpot


echo
echo
echo "Please reboot for the hotspot changes to take effect"
echo
echo
echo "SSID: $HOTSPOT_SSID"
echo "PSK:  $HOTSPOT_PSK"
echo
echo "Band:    $HOTSPOT_BAND"
echo "Channel: $HOTSPOT_CHANNEL"
echo
echo "Indi-Allsky HotSpot IP:  $HOTSPOT_IP  (255.255.255.0)"
echo "URL: https://${HOTSPOT_IP}/"
echo


