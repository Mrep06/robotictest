import rclpy
from rclpy.node import Node
from geometry_msgs.msg import Twist
from trajectory_msgs.msg import JointTrajectory, JointTrajectoryPoint
from builtin_interfaces.msg import Duration
from linkattacher_msgs.srv import AttachLink, DetachLink # <--- เพิ่ม Import สำหรับ Service ของปลั๊กอิน
import sys, select, termios, tty

# คำอธิบายปุ่มควบคุม (เพิ่ม c และ v เข้ามา)
msg = """
Control Your Robot and Arm!
---------------------------
Moving Robot (Base):        Moving Arm (Lift/Grip):
    w : Forward                 i : Arm Up (+0.01)
    s : Backward                k : Arm Down (-0.01)
    a : Left                    j : Slide In (+0.01)
    d : Right                   l : Slide Out (-0.01)

Plugin (Grasp):
    c : Attach Object (จับวัตถุ)
    v : Detach Object (ปล่อยวัตถุ)

space or x : Stop All (Robot & Arm)
CTRL-C to quit
"""

class CombinedTeleop(Node):
    def __init__(self):
        super().__init__('combined_teleop')
        # Publisher สำหรับล้อ
        self.wheel_pub = self.create_publisher(Twist, 'cmd_vel', 10)
        # Publisher สำหรับแขน
        self.arm_pub = self.create_publisher(JointTrajectory, '/arm_controller/joint_trajectory', 10)
        
        # สร้าง Service Client สำหรับสั่งจับและปล่อย (Plugin IFRA Link Attacher)
        self.attach_cli = self.create_client(AttachLink, '/ATTACHLINK')
        self.detach_cli = self.create_client(DetachLink, '/DETACHLINK')
        
        # สถานะเริ่มต้นของแขน
        self.base2_pos = 0.0
        self.slide_pos = 0.0
        
        # ขีดจำกัด (Limits) จาก URDF
        self.base2_limit = [0.0, 0.2]
        self.slide_limit = [0.0, 0.25375]

    def send_arm_command(self):
        trajectory_msg = JointTrajectory()
        trajectory_msg.joint_names = ['arm_base2_joint', 'arm_slide_joint_L', 'arm_slide_joint_R']
        
        point = JointTrajectoryPoint()
        # Slide R จะเป็นค่าลบตามที่ตั้งไว้ใน xacro
        point.positions = [self.base2_pos, self.slide_pos, -self.slide_pos]
        point.time_from_start = Duration(sec=0, nanosec=100000000) # 0.1 sec
        
        trajectory_msg.points.append(point)
        self.arm_pub.publish(trajectory_msg)

    def send_wheel_command(self, linear, angular):
        twist = Twist()
        twist.linear.x = linear
        twist.angular.z = angular
        self.wheel_pub.publish(twist)

    # ฟังก์ชันสำหรับจับวัตถุ
    def attach_object(self):
        if not self.attach_cli.wait_for_service(timeout_sec=1.0):
            self.get_logger().warn('ATTACHLINK service not available!')
            return
            
        req = AttachLink.Request()
        req.model1_name = 'robot779'      # ชื่อหุ่นยนต์ของคุณใน Gazebo
        req.link1_name = 'arm_slide_L'    # ชื่อ Link ปลายแขนของหุ่น (ต้องแก้ให้ตรงกับ URDF ของคุณ)
        req.model2_name = 'box_final1'    # ชื่อวัตถุเป้าหมายใน Gazebo
        req.link2_name = 'link_1'       # ชื่อ Link ของวัตถุเป้าหมาย
        
        self.attach_cli.call_async(req)
        print("\n--> Sent ATTACH command! (พยายามจับวัตถุ)\n")

    # ฟังก์ชันสำหรับปล่อยวัตถุ
    def detach_object(self):
        if not self.detach_cli.wait_for_service(timeout_sec=1.0):
            self.get_logger().warn('DETACHLINK service not available!')
            return
            
        req = DetachLink.Request()
        req.model1_name = 'robot779'
        req.link1_name = 'arm_slide_L'
        req.model2_name = 'box_final1'
        req.link2_name = 'link_1'
        
        self.detach_cli.call_async(req)
        print("\n--> Sent DETACH command! (ปล่อยวัตถุ)\n")

def get_key(settings):
    tty.setraw(sys.stdin.fileno())
    select.select([sys.stdin], [], [], 0.1)
    key = sys.stdin.read(1)
    termios.tcsetattr(sys.stdin, sys.stdin.fileno(), settings)
    return key

def main():
    settings = termios.tcgetattr(sys.stdin)
    rclpy.init()
    node = CombinedTeleop()
    
    print(msg)
    
    try:
        while True:
            key = get_key(settings)
            
            # ควบคุมล้อ (Base)
            if key == 'w':
                node.send_wheel_command(0.5, 0.0)
            elif key == 's':
                node.send_wheel_command(-0.5, 0.0)
            elif key == 'a':
                node.send_wheel_command(0.0, 1.0)
            elif key == 'd':
                node.send_wheel_command(0.0, -1.0)
            
            # ควบคุมแขน (Arm)
            elif key == 'i':
                node.base2_pos = min(node.base2_limit[1], node.base2_pos + 0.01)
                node.send_arm_command()
            elif key == 'k':
                node.base2_pos = max(node.base2_limit[0], node.base2_pos - 0.01)
                node.send_arm_command()
            elif key == 'j':
                node.slide_pos = min(node.slide_limit[1], node.slide_pos + 0.01)
                node.send_arm_command()
            elif key == 'l':
                node.slide_pos = max(node.slide_limit[0], node.slide_pos - 0.01)
                node.send_arm_command()
                
            # ปุ่มสำหรับจับ/ปล่อยวัตถุ (c/v)
            elif key == 'c':
                node.attach_object()
            elif key == 'v':
                node.detach_object()
                
            # หยุดทุกอย่าง
            elif key in [' ', 'x']:
                node.send_wheel_command(0.0, 0.0)
                node.base2_pos = 0.0
                node.slide_pos = 0.0
                node.send_arm_command()
                
            elif key == '\x03': # CTRL-C
                break
            
            if key != '':
                print(f"Pos -> Base2: {node.base2_pos:.2f}, Slide: {node.slide_pos:.2f} | Key: {key}", end='\r')

    except Exception as e:
        print(e)
    finally:
        node.destroy_node()
        rclpy.shutdown()
        termios.tcsetattr(sys.stdin, sys.stdin.fileno(), settings)

if __name__ == '__main__':
    main()