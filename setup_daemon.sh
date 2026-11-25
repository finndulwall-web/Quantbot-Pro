#!/data/data/com.termux/files/usr/bin/bash
set -e

echo "========================================="
echo "QuantBot Pro Daemon Setup (4GB RAM Headless)"
echo "========================================="

BOT_DIR="/opt/quantbot"
SERVICE_USER="quantbot"

echo "Creating bot user..."
id -u $SERVICE_USER &>/dev/null || useradd -r -s /bin/false -d $BOT_DIR $SERVICE_USER

echo "Creating directory structure..."
mkdir -p $BOT_DIR/{logs,data,core,ui,utils}
chown -R $SERVICE_USER:$SERVICE_USER $BOT_DIR

echo "Copying bot files..."
cp -r . $BOT_DIR/
chown -R $SERVICE_USER:$SERVICE_USER $BOT_DIR

echo "Installing system dependencies..."
apt-get update && apt-get install -y python3 python3-pip python3-venv git curl

echo "Creating virtual environment..."
sudo -u $SERVICE_USER python3 -m venv $BOT_DIR/venv
sudo -u $SERVICE_USER $BOT_DIR/venv/bin/pip install --upgrade pip setuptools wheel

echo "Installing Python dependencies..."
sudo -u $SERVICE_USER $BOT_DIR/venv/bin/pip install -r $BOT_DIR/requirements.txt

echo "Installing gunicorn for UI..."
sudo -u $SERVICE_USER $BOT_DIR/venv/bin/pip install gunicorn

echo "Setting up log rotation..."
cat > /etc/logrotate.d/quantbot << EOF
$BOT_DIR/bot.log {
    daily
    rotate 7
    compress
    delaycompress
    missingok
    notifempty
    create 640 $SERVICE_USER $SERVICE_USER
    maxsize 10M
}
EOF

echo "Installing systemd service..."
cp $BOT_DIR/quantbot.service /etc/systemd/system/
cp $BOT_DIR/quantbot-ui.service /etc/systemd/system/
cp $BOT_DIR/quantbot-watchdog.service /etc/systemd/system/

systemctl daemon-reload
systemctl enable quantbot quantbot-ui quantbot-watchdog

echo "========================================="
echo "Daemon setup complete!"
echo "========================================="
echo ""
echo "Start services:"
echo "  systemctl start quantbot quantbot-ui quantbot-watchdog"
echo ""
echo "Check status:"
echo "  systemctl status quantbot"
echo "  systemctl status quantbot-ui"
echo "  systemctl status quantbot-watchdog"
echo ""
echo "View logs:"
echo "  journalctl -u quantbot -f"
echo "  journalctl -u quantbot-ui -f"
echo "  journalctl -u quantbot-watchdog -f"
echo ""
echo "UI accessible at: http://<server-ip>:8080"
echo "========================================="
