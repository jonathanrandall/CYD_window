import time
import board
import busio
from adafruit_pca9685 import PCA9685

# Setup I2C
i2c = busio.I2C(board.SCL, board.SDA)

# Setup PCA9685
pca = PCA9685(i2c)
pca.frequency = 50   # 50Hz for servos

def set_servo(channel, pulse):
    pca.channels[channel].duty_cycle = pulse

while True:

    # move one direction between 2000 and 8000
    for pulse in range(2000, 8000, 100):
        set_servo(14, pulse)
        set_servo(15, 10000 - pulse)
        time.sleep(0.05)

    # move back
    for pulse in range(8000, 2000, -100):
        set_servo(14, pulse)
        set_servo(15, 10000 - pulse) #higher to the left
        time.sleep(0.05)
