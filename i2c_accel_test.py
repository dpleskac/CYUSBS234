from cyusbs23x import *

b = UsbBridge()
eeprom_addr = 0x6b

e = I2cMemDev(b,eeprom_addr)
e.dump(2)


