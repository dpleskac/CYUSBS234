from cyusbs23x import *

b = UsbBridge()

eeprom_addr = 0x6b
a = I2cMemDev(b, eeprom_addr, 1)

a.dump(2)
