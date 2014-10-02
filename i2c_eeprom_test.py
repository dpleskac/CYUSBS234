from cyusbs23x import *

b = UsbBridge()

eeprom_addr = 0x51
e = I2cEeprom(b,eeprom_addr)

e.dump(2)

#data = array('B', range(0, 32))
#e.write(0x10, data)
#e.dump(2)

