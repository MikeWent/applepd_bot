#!/bin/bash

name="applepd_bot"

systemctl stop "$name.service" 2> /dev/null # hide output if service doesn't exist

echo "[Unit]
Description=applepd_bot Telegram bot
Documentation=https://github.com/MikeWent/applepd_bot
Wants=network-online.target
After=network.target network-online.target

[Service]
Type=simple
ExecStart=/usr/bin/python3 $PWD/bot.py
Restart=always
RestartSec=5
User=$USER
WorkingDirectory=$PWD

[Install]
WantedBy=multi-user.target" > $name.service

mv $name.service /lib/systemd/system/
systemctl daemon-reload
systemctl enable "$name.service"
systemctl start "$name.service"
echo "Service '$name.service' started and enabled on startup"
