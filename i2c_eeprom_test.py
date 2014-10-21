from cyusbs23x import *

b = UsbBridge()

eeprom_addr = 0x51
e = I2cMemDev(b,eeprom_addr)

e.dump(4)

#data = array('B', range(0, 32))
#e.write(0x10, data)
#e.dump(2)

