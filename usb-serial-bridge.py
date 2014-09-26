from usb.core import *
from usb.util import *
from array import array
from binascii import hexlify

# find our device
dev = find(idVendor=0x04b4, idProduct=0x0004)

# was it found?
if dev is None:
    raise ValueError('Device not found')

# set the active configuration. With no arguments, the first
# configuration will be the active one
dev.set_configuration()

cfg = dev.get_active_configuration()
if cfg is None:
    raise ValueError('Configuration not found')

intf = find_descriptor(cfg, bInterfaceSubClass=3)
if intf is None:
    raise ValueError('Interface not found')

ep_intr = find_descriptor(intf, \
		custom_match = lambda e: endpoint_direction(e.bEndpointAddress) == ENDPOINT_IN, 
		bmAttributes=ENDPOINT_TYPE_INTR)

ep_bulk_i = find_descriptor(intf, \
		custom_match = lambda e: endpoint_direction(e.bEndpointAddress) == ENDPOINT_IN, \
		bmAttributes=ENDPOINT_TYPE_BULK)

ep_bulk_o = find_descriptor(intf, \
		custom_match = lambda e: endpoint_direction(e.bEndpointAddress) == ENDPOINT_OUT, \
		bmAttributes=ENDPOINT_TYPE_BULK)

print ep_bulk_i
print ep_bulk_o
print ep_intr

DEVICE_TO_HOST = 0xC0
HOST_TO_DEVICE = 0x40

I2C_WRITE_CMD          = 0xC6
I2C_READ_CMD           = 0xC7
I2C_GET_STATUS_CMD     = 0xC8
I2C_GET_STATUS_CMD_LEN = 3
I2C_RESET_CMD          = 0xC9
I2C_RESET_CMD_LEN      = 0


def i2c_reset():	
	# reset read
	sts = dev.ctrl_transfer(DEVICE_TO_HOST, I2C_RESET_CMD, 0, 0, I2C_RESET_CMD_LEN)
	# reset write
	sts = dev.ctrl_transfer(DEVICE_TO_HOST, I2C_RESET_CMD, 1, 0, I2C_RESET_CMD_LEN)

def i2c_status_ok():
	I2C_ERROR_BIT = 0x01
	sts = dev.ctrl_transfer(DEVICE_TO_HOST, I2C_GET_STATUS_CMD, 0, 0, I2C_GET_STATUS_CMD_LEN)
	if sts[0] & I2C_ERROR_BIT:
		print "Device busy"
		return False;

def i2c_wait_for_interrupt():
	ep_intr.read(3)

def i2c_write(dev_addr, data):
	if i2c_status_ok() is False:
		exit
	# FIXME - hardcoded start=1, stop=0
	dev.ctrl_transfer(HOST_TO_DEVICE, I2C_WRITE_CMD, ((dev_addr << 8) | 0x01), len(data), 0)
	ep_bulk_o.write(data, len(data))
	i2c_wait_for_interrupt()

def i2c_read(dev_addr, length):
	if i2c_status_ok() is False:
		exit
	data = array('B',[])
	# FIXME - hardcoded start=1, stop=1
	dev.ctrl_transfer(HOST_TO_DEVICE, I2C_READ_CMD, ((dev_addr << 8) | 0x03), length, 0)
	data = ep_bulk_i.read(length)
	i2c_wait_for_interrupt()
	return data


eeprom_addr = 0x51

def i2c_eeprom_write(addr, data):
	# add address (first 2 bytes)
	data.insert(0, (addr & 0xff))
	data.insert(0, ((addr & 0xff00) >> 8))
	i2c_write(eeprom_addr, data)

def i2c_eeprom_read(addr, length):
	# start clean
	i2c_reset()
	# write address page
	data = array('B', [((addr & 0xff00) >> 8), (addr & 0xff)])
	i2c_write(eeprom_addr, data)
	# read data
	return i2c_read(eeprom_addr, length)

def i2c_eeprom_dump(lines):
	for line in range(0,lines):
		addr = line*32
		print hex(addr), hexlify(i2c_eeprom_read(addr, 32))
	print

data = array('B', range(0, 32))
i2c_eeprom_write(0x3fe0, data)

#data = array('B', range(32, 64))
#i2c_eeprom_write(32, data)
#i2c_eeprom_dump()

i2c_eeprom_dump(512)

'''
usbmon trace test-utility

WRITE
 S Ci:6:002:0 s c0 c8 0001 0000 0003 3 <
 C Ci:6:002:0 0 3 = 800000

 S Co:6:002:0 s 40 c6 5101 0022 0000 0
 C Co:6:002:0 0 0
 S Bo:6:002:1 -115 34 = 000067c6 697351ff 4aec29cd baabf2fb e3467cc2 54f81be8 e78d765a 2e63339f
 C Bo:6:002:1 0 34 >
 S Ii:6:002:3 -115:8 3 <
 C Ii:6:002:3 0:8 3 = 800000

 S Ci:6:002:0 s c0 c8 0001 0000 0003 3 <
 C Ci:6:002:0 0 3 = 800000

 S Co:6:002:0 s 40 c6 5100 0002 0000 0
 C Co:6:002:0 0 0
 S Bo:6:002:1 -115 2 = 0000
 C Bo:6:002:1 0 2 >
 S Ii:6:002:3 -115:8 3 <
 C Ii:6:002:3 0:8 3 = a00000

READ
 S Ci:6:002:0 s c0 c8 0000 0000 0003 3 <
 C Ci:6:002:0 0 3 = 200000

 S Co:6:002:0 s 40 c7 5103 0020 0000 0
 C Co:6:002:0 0 0
 S Bi:6:002:2 -115 32 <
 C Bi:6:002:2 0 32 = 67c66973 51ff4aec 29cdbaab f2fbe346 7cc254f8 1be8e78d 765a2e63 339fc99a
 S Ii:6:002:3 -115:8 3 <
 C Ii:6:002:3 0:8 3 = 000000

'''
