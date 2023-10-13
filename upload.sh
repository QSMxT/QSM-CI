set -e

# Check if Python is installed and if not install it
if command -v python >/dev/null 2>&1; then
    echo "Python is already installed."
else
    echo "Python is not installed. Installing..."
    sudo apt-get update
    sudo apt-get install python3 python-is-python3 -y
fi

# install dependencies
echo "[INFO] Downloading dependencies"
pip install qsm-forward==0.11 webdavclient3
export PATH=$PATH:/home/runnerx/.local/bin

sudo apt-get update
sudo apt-get install tree

# download head-phantom-maps
echo "[INFO] Downloading test data"
python get-maps.py
tar xf head-phantom-maps.tar

