import os

from launch import LaunchDescription
from launch.actions import (
    DeclareLaunchArgument,
    OpaqueFunction,
    IncludeLaunchDescription,
    RegisterEventHandler,
)
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration
from ament_index_python.packages import get_package_share_directory
from launch_ros.actions import Node
from launch.conditions import IfCondition
from time import sleep
from launch.event_handlers import OnShutdown


def launch_setup(context, *args, **kwargs):
    # initialize arguments
    sim_ignition = LaunchConfiguration("sim_ignition")

    # paths
    pkg_share = get_package_share_directory("scout_description")
    sdf_file = os.path.join(pkg_share, "urdf", "output.sdf")
    urdf_file = os.path.join(pkg_share, "urdf", "output.urdf")

    # read the robot description from the urdf file
    with open(urdf_file, 'r') as infp:
        robot_description_content = infp.read()

    robot_description = {"robot_description": robot_description_content}

    # start ignition gazebo
    ignition_launch_description = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            os.path.join(
                get_package_share_directory("ros_gz_sim"),
                "launch",
                "gz_sim.launch.py",
            )
        ),
        launch_arguments={"gz_args": "-r -v 3"}.items(),
        condition=IfCondition(sim_ignition),
    )
    sleep(2)
    # spawn entity into ignition gazebo
    spawn_entity = Node(
        package="ros_gz_sim",
        executable="create",
        output="screen",
        arguments=[
            "-file",
            sdf_file,
            "-name",
            "scout_kinova",
            "-allow_renaming",
            "true",
            "-x",
            "0.0",
            "-y",
            "0.0",
            "-z",
            "500",
            "-R",
            "0.0",
            "-P",
            "0.0",
            "-Y",
            "0.0",
        ],
        condition=IfCondition(sim_ignition),
    )

    # controller node
    ros2_controllers_path = os.path.join(
        pkg_share,
        "config",
        "ros2_controllers.yaml",
    )
    ros2_control_node = Node(
        package="controller_manager",
        executable="ros2_control_node",
        parameters=[robot_description, ros2_controllers_path],
        output="screen",
        remappings=[
            ("/joint_states", "/scout_kinova/joint_states"),
        ],
    )

    # other nodes
    robot_state_publisher = Node(
        package="robot_state_publisher",
        executable="robot_state_publisher",
        name="robot_state_publisher",
        output="both",
        parameters=[robot_description],
    )

    static_tf2 = Node(
        package="tf2_ros",
        executable="static_transform_publisher",
        name="static_transform_publisher",
        output="log",
        arguments=["--frame-id", "world", "--child-frame-id", "base_link"],
    )

    robot_traj_controller_spawner = Node(
        package="controller_manager",
        executable="spawner",
        arguments=["joint_trajectory_controller", "-c", "/controller_manager"],
    )

    robot_pos_controller_spawner = Node(
        package="controller_manager",
        executable="spawner",
        arguments=["twist_controller", "--inactive", "-c", "/controller_manager"],
    )

    joint_state_broadcaster_spawner = Node(
        package="controller_manager",
        executable="spawner",
        arguments=[
            "joint_state_broadcaster",
            "--controller-manager",
            "/controller_manager",
        ],
    )

    # ros_gz_bridge node to bridge topics
    bridge = Node(
        package="ros_gz_bridge",
        executable="parameter_bridge",
        arguments=[
            "/clock@rosgraph_msgs/msg/Clock@ignition.msgs.Clock",
            # add other topics to bridge if necessary
        ],
        output="screen",
    )

    # event handlers for shutdown
    def on_shutdown(event, context):
        print("shutting down gracefully...")

    shutdown_handler = RegisterEventHandler(
        OnShutdown(
            on_shutdown=[
                ignition_launch_description,
                spawn_entity,
                bridge,
                ros2_control_node,
                robot_state_publisher,
                joint_state_broadcaster_spawner,
                robot_traj_controller_spawner,
                robot_pos_controller_spawner,
                static_tf2,
            ]
        )
    )

    nodes_to_start = [
        ignition_launch_description,
        spawn_entity,
        bridge,
        ros2_control_node,
        robot_state_publisher,
        joint_state_broadcaster_spawner,
        robot_traj_controller_spawner,
        robot_pos_controller_spawner,
        static_tf2,
        shutdown_handler,
    ]

    return nodes_to_start


def generate_launch_description():
    # declare arguments
    declared_arguments = []
    declared_arguments.append(
        DeclareLaunchArgument(
            "sim_ignition",
            default_value="true",
            description="use ignition gazebo for simulation",
        )
    )

    return LaunchDescription(declared_arguments + [OpaqueFunction(function=launch_setup)])
