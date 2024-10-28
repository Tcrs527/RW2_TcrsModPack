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

Level.EventOnMakeFloor = namedtuple("EventOnMakeFloor", "x y was_chasm was_wall")

def make_floor_event(self, x, y, calc_glyph=True):
		tile = self.tiles[x][y]
		was_chasm = False
		was_wall = False
		if tile.is_chasm:
			was_chasm = True
		if tile.is_wall():
			was_wall = True
		tile.can_walk = True
		tile.can_see = True
		tile.can_fly = True
		tile.is_chasm = False
		tile.name = "Floor"
		tile.description = "A rough rocky floor"

		if self.brush_tileset:
			tile.tileset = self.brush_tileset

		if calc_glyph:
			tile.calc_glyph()

		self.clear_tile_sprite(tile)

		if self.tcod_map:
			libtcod.map_set_properties(self.tcod_map, tile.x, tile.y, tile.can_see, tile.can_walk)
		
		
		self.event_manager.raise_event(Level.EventOnMakeFloor(x, y , was_chasm, was_wall))

Level.make_floor = make_floor_event