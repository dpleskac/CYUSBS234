from usb.core import *
from usb.util import *
from array import array
from binascii import hexlify

class UsbBridge:
    ''' Usb-Serial Bridge driver '''

    __DEVICE_TO_HOST = 0xC0
    __HOST_TO_DEVICE = 0x40
    __I2C_WRITE_CMD          = 0xC6
    __I2C_READ_CMD           = 0xC7
    __I2C_GET_STATUS_CMD     = 0xC8
    __I2C_GET_STATUS_CMD_LEN = 3
    __I2C_RESET_CMD          = 0xC9
    __I2C_RESET_CMD_LEN      = 0

    def __init__(self, debug = None):
        self.dev = find(idVendor=0x04b4, idProduct=0x0004)
        if self.dev is None:
            raise ValueError('Device not found')
        self.dev.set_configuration()
        cfg = self.dev.get_active_configuration()
        if cfg is None:
            raise ValueError('Configuration not found')
        intf = find_descriptor(cfg, bInterfaceSubClass=3)
        if intf is None:
            raise ValueError('Interface not found')
        self.ep_intr = find_descriptor(intf, \
                custom_match = lambda e: endpoint_direction(e.bEndpointAddress) == ENDPOINT_IN, \
                bmAttributes=ENDPOINT_TYPE_INTR)
        self.ep_bulk_i = find_descriptor(intf, \
                custom_match = lambda e: endpoint_direction(e.bEndpointAddress) == ENDPOINT_IN, \
                bmAttributes=ENDPOINT_TYPE_BULK)
        self.ep_bulk_o = find_descriptor(intf, \
                custom_match = lambda e: endpoint_direction(e.bEndpointAddress) == ENDPOINT_OUT, \
                bmAttributes=ENDPOINT_TYPE_BULK)
        if debug is not None:
            print self.ep_bulk_i
            print self.ep_bulk_o
            print self.ep_intr

    def i2c_reset(self):	
        # reset read
        sts = self.dev.ctrl_transfer(self.__DEVICE_TO_HOST, self.__I2C_RESET_CMD, 0, 0, self.__I2C_RESET_CMD_LEN)
        # reset write
        sts = self.dev.ctrl_transfer(self.__DEVICE_TO_HOST, self.__I2C_RESET_CMD, 1, 0, self.__I2C_RESET_CMD_LEN)

    def i2c_status_ok(self, debug=None):
        __I2C_ERROR_BIT = 0x01
        sts = self.dev.ctrl_transfer(self.__DEVICE_TO_HOST, self.__I2C_GET_STATUS_CMD, 0, 0, self.__I2C_GET_STATUS_CMD_LEN)
        if debug is not None:
            print "Status:", hex(sts[0]), hex(sts[1]), hex(sts[2])
        if sts[0] & __I2C_ERROR_BIT:
            print "Device busy"
            return False;

    def i2c_wait_for_interrupt(self):
        self.ep_intr.read(3)

    def i2c_write(self, dev_addr, data, start=1, stop=0):
        '''
         usbmon trace:
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
        '''
        if self.i2c_status_ok() is False:
            exit
        # send i2c write command
        self.dev.ctrl_transfer(self.__HOST_TO_DEVICE, \
                               self.__I2C_WRITE_CMD, \
                               ((dev_addr << 8) | ((stop & 1) << 1) | (start & 1)), \
                               len(data), 0)
        self.ep_bulk_o.write(data, len(data))
        self.i2c_wait_for_interrupt()

    def i2c_read(self, dev_addr, length, start=1, stop=1):
        '''
         usbmon trace:
             S Ci:6:002:0 s c0 c8 0000 0000 0003 3 <
             C Ci:6:002:0 0 3 = 200000

             S Co:6:002:0 s 40 c7 5103 0020 0000 0
             C Co:6:002:0 0 0
             S Bi:6:002:2 -115 32 <
             C Bi:6:002:2 0 32 = 67c66973 51ff4aec 29cdbaab f2fbe346 7cc254f8 1be8e78d 765a2e63 339fc99a
             S Ii:6:002:3 -115:8 3 <
             C Ii:6:002:3 0:8 3 = 000000
        '''
        if self.i2c_status_ok() is False:
            exit
        data = array('B',[])
        # send i2c read command
        self.dev.ctrl_transfer(self.__HOST_TO_DEVICE, \
                               self.__I2C_READ_CMD, \
                               ((dev_addr << 8) | ((stop & 1) << 1) | (start & 1)), \
                               length, 0)
        data = self.ep_bulk_i.read(length)
        self.i2c_wait_for_interrupt()
        return data


class I2cMemDev:
    def __init__(self, usb_bridge, addr, num_addr_bytes = 2):
        self.ub = usb_bridge
        self.eeprom_addr = addr
        self.addr_bytes = num_addr_bytes
        self.rd_start = 1
        self.rd_stop  = 1
        self.wr_start = 1
        self.wr_stop  = 0

    def write(self, addr, data):
        ''' 
            Memory write - sends one write message with 
                           2 byte address followed by data
        '''
        if ((addr + len(data) - 1) >= pow(256, self.addr_bytes)):
            raise ValueError('Address range exceeded')
        # add address (first n bytes)
        for shift in range(0, self.addr_bytes * 8, 8):
            data.insert(0, ((addr >> shift) & 0xff))
        self.ub.i2c_write(self.eeprom_addr, data, self.wr_start, self.wr_stop)

    def read(self, addr, length):
        ''' 
            Memory read - sends one write message with 
                           2 byte address followed by 
                           read message to retrieve data
        '''
        if ((addr + length - 1) >= pow(256, self.addr_bytes)):
            raise ValueError('Address range exceeded')
        # start clean
        self.ub.i2c_reset()
        # write address page
        data = array('B', [])
        for shift in range(0, self.addr_bytes * 8, 8):
            data.insert(0, ((addr >> shift) & 0xff))
        self.ub.i2c_write(self.eeprom_addr, data, self.wr_start, self.wr_stop)
        # read data
        return self.ub.i2c_read(self.eeprom_addr, length, self.rd_start, self.rd_stop)

    def dump(self, lines):
        print ''.rjust(9), 2 * '0   2   4   6   8   a   c   e   '
        for line in range(0,lines):
            addr = line*32
            print hex(addr).rjust(8) + ":", hexlify(self.read(addr, 32))
        print

