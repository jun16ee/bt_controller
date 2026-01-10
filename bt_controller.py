import serial
import time
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class ESP32BTSender:
    CMD_MAP = { "RESET": 0x01, "READY": 0x02, "TEST": 0x03, "PLAY": 0xA0, "PAUSE": 0xA1 }

    def __init__(self, port, baud_rate=115200, timeout=1):
        self.port = port
        self.baud_rate = baud_rate
        self.timeout = timeout
        self.ser = None

    def connect(self):
        try:
            self.ser = serial.Serial(self.port, self.baud_rate, timeout=self.timeout)
            time.sleep(2)
            self.ser.reset_input_buffer()
            logger.info(f"Connected to {self.port}")
        except serial.SerialException as e:
            logger.error(f"Failed to connect: {e}")
            raise

    def close(self):
        if self.ser and self.ser.is_open:
            self.ser.close()

    def send_burst(self, cmd_input, delay_sec, target_ids, retries=3):
        if not self.ser or not self.ser.is_open:
            return False

        cmd_int = cmd_input if isinstance(cmd_input, int) else self.CMD_MAP.get(cmd_input, 0)
        delay_us = int(delay_sec * 1_000_000)
        target_mask = 0
        for pid in target_ids:
            target_mask |= (1 << pid)

        # 格式: 160,1000000,23 (最後的 23 是 Hex)
        packet = f"{cmd_int},{delay_us},{target_mask:x}\n"

        for attempt in range(retries + 1):
            if attempt > 0:
                logger.warning(f"Retrying... ({attempt}/{retries})")
                time.sleep(0.2)

            logger.info(f"Sending: {packet.strip()}")
            
            try:
                self.ser.reset_input_buffer() # 發送前清空舊雜訊
                self.ser.write(packet.encode('utf-8'))

                # 等待 ACK (雖然沒有 Checksum，但確認收到還是必要的)
                start_time = time.time()
                while (time.time() - start_time) < (delay_sec + 2.0):
                    if self.ser.in_waiting:
                        line = self.ser.readline().decode('utf-8', errors='ignore').strip()
                        
                        if "ACK:OK" in line:
                            logger.info(f"Success: {line}")
                            return True
                        elif "NAK" in line:
                            logger.warning(f"Device rejected command: {line}")
                            break 
            except Exception as e:
                logger.error(f"Error: {e}")

        logger.error("Failed to send command after retries.")
        return False

    def __enter__(self):
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()