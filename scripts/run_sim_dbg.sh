cd /home/fangzhou/projects/LC_01

/home/fangzhou/Nvidia/isaacsim-git/isaacsim/_build/linux-x86_64/release/python.sh \
  -m debugpy \
  --listen 5678 \
  --wait-for-client \
  src/simworld/main.py \
#   --scene_usd /path/to/base_scene.usd \
#   --robot_usd /path/to/robot.usd \
#   --asset_usd /path/to/object.usd