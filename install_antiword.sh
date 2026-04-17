#!/bin/bash
# Script cài antiword để đọc file .doc

echo "Cài antiword..."
sudo apt-get update
sudo apt-get install -y antiword

echo "Kiểm tra cài đặt:"
antiword -v

echo "Xong! Giờ có thể đọc file .doc"
