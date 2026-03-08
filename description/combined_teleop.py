import rclpy
from rclpy.node import Node
from geometry_msgs.msg import Twist
from trajectory_msgs.msg import JointTrajectory, JointTrajectoryPoint
from builtin_interfaces.msg import Duration
import sys, select, termios, tty

# คำอธิบายปุ่มควบคุม
msg = """
Control Your Robot and Arm!
---------------------------
Moving Robot (Base):        Moving Arm (Lift/Grip):
    w : Forward                 i : Arm Up (+0.01)
    s : Backward                k : Arm Down (-0.01)
    a : Left                    j : Slide In (+0.01)
    d : Right                   l : Slide Out (-0.01)

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