

import sys
from tokenize import String
sys.path.append('../..')
import time
from Equipment import *
from Level import *
import mods.TcrsCustomModpack.CustomSpells as cust_spells
import mods.TcrsCustomModpack.CustomSkills as cust_skills

print("TCRS's Custom Modpack Loaded.")
print(time.asctime())

cust_spells.construct_spells()
cust_skills.construct_skills()

#print("Testing")
#for a in RiftWizard.__dir__():
#	print(a)
#print("Testing")

# def add_events():
# 	Level.EventOnMakeFloor = namedtuple("EventOnMakeFloor", "x y")
# add_events()

# def make_floor_event(self, x, y, calc_glyph=True):
# 		tile = self.tiles[x][y]
# 		tile.can_walk = True
# 		tile.can_see = True
# 		tile.can_fly = True
# 		tile.is_chasm = False
# 		tile.name = "Floor"
# 		tile.description = "A rough rocky floor"

# 		if self.brush_tileset:
# 			tile.tileset = self.brush_tileset

# 		if calc_glyph:
# 			tile.calc_glyph()

# 		self.clear_tile_sprite(tile)

# 		if self.tcod_map:
# 			libtcod.map_set_properties(self.tcod_map, tile.x, tile.y, tile.can_see, tile.can_walk)
			
# 		self.event_manager.raise_event(EventOnMakeFloor(x, y))

# def new_func():
#     Level.make_floor = make_floor_event
# new_func()

#from RiftWizard2 import main_view

import inspect #                                  |
def get_RiftWizard(): #                           |
   # Returns the RiftWizard.py module object      |
   for f in inspect.stack()[::-1]: #              |
       if "file 'RiftWizard2.py'" in str(f): #    |
           return inspect.getmodule(f[0]) #       |
	#                                             |
   return inspect.getmodule(f[0]) #               |
RiftWizard = get_RiftWizard() #   


def draw_cloud_mod(self, cloud, secondary=False):
	print("testing")
	if not cloud.asset_name:
		return

	if type(cloud.asset_name) == list:
		asset = filename
	elif secondary:
		filename = cloud.asset_name + '_2'
	else:
		filename = cloud.asset_name + '_1'
		asset = "TEST" #Obviously fix this later

	if type(asset) == String:
		asset = ['tiles', 'clouds', filename]
	elif type(asset) == list:
		asset = filename

	image = get_image(asset)

	num_frames = image.get_width() // sprite_size
	cur_frame = (cloud_frame_clock // sub_frames[anim_idle]) % num_frames

	subarea = (sprite_size * cur_frame, 0, sprite_size, sprite_size)

	x = cloud.x * sprite_size
	y = cloud.y * sprite_size

	self.level_display.blit(image, (x, y), subarea)


pygameview_draw_cloud = RiftWizard.PyGameView.draw_cloud
def pygameview_draw_cloud(self, *args, **kwargs):
	pygameview_draw_cloud(self, *args, **kwargs)
	self.draw_cloud = self.draw_cloud_mod
RiftWizard.PyGameView.draw_cloud = draw_cloud_mod

# import inspect
# from RiftWizard2 import main_view

# Tags.elements.append(Tag("Water", Color(14, 14, 250)))
# damage_tags.append(Tags.Water)

# __pygameview_init_old = RiftWizard.PyGameView.__init__
# def pygameview_init(self, *args, **kwargs):
# 	__pygameview_init_old(self, *args, **kwargs)
# 	#self.tag_keys['q'] = Tags.Water
# 	#self.reverse_tag_keys = {v:k.upper() for k, v in self.tag_keys.items()}
# 	#API_OptionsMenu.try_initialize_options(self)
# 	#API_Spells.pygameview_init(self)
# RiftWizard.PyGameView.__init__ = pygameview_init

#Knowledges.append(Tags.Water)
#main_view.tag_keys['h'] = Tags.water