import sys
from tokenize import String
sys.path.append('../..')
import time
from Equipment import *
from Level import *
from LevelGen import LevelGenerator, LEVEL_SIZE
import mods.TcrsCustomModpack.CustomSpells as cust_spells
import mods.TcrsCustomModpack.CustomSkills as cust_skills

print("TCRS's Custom Modpack Loaded.")
print(time.asctime())

cust_spells.construct_spells()
cust_skills.construct_skills()

## Modifications to make_floor so that walls or chasms becoming floors can be events
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

## Modifications to add_obj_event so that clouds entering can be events
Level.EventOnMakeCloud = namedtuple("EventOnCloudEnter", "x y cloud")
Level.EventOnMakeProp = namedtuple("EventOnPropEnter", "x y prop")

def add_obj_event(self, obj, x, y):
		obj.x = x
		obj.y = y
		obj.level = self

		if not hasattr(obj, 'level_id'):
			obj.level_id = self.level_id

		if isinstance(obj, Unit):
			self.event_manager.raise_event(EventOnUnitPreAdded(obj), obj)

			if obj.max_hp <= 1:
				obj.max_hp = 1

			if not obj.cur_hp:
				obj.cur_hp = obj.max_hp
				assert(obj.cur_hp > 0)
				
			
			for i in range(-obj.radius, obj.radius+1):
				for j in range(-obj.radius, obj.radius+1):
					cur_x = x + i
					cur_y = y + j

					if not self.tiles[cur_x][cur_y].unit is None:
						print("Cannot add %s at %s, already has %s" % (obj.name, str((x, y)), self.tiles[cur_x][cur_y].unit.name))
						assert(self.tiles[cur_x][cur_y].unit is None)

					self.tiles[cur_x][cur_y].unit = obj

			# Hack- allow improper adding in monsters.py
			for spell in obj.spells:
				spell.caster = obj
				spell.owner = obj

			self.set_default_resistances(obj)

			for buff in list(obj.buffs):
				# Apply unapplied buffs- these can come from Content on new units
				could_apply = buff.apply(obj) != ABORT_BUFF_APPLY

				# Remove buffs which cannot be applied (happens with stun + clarity potentially)
				if not could_apply:
					obj.buffs.remove(obj)

				# Monster buffs are all passives
				if not obj.is_player_controlled:
					buff.buff_type = BUFF_TYPE_PASSIVE

			self.units.append(obj)
			self.event_manager.raise_event(EventOnUnitAdded(obj), obj)

			obj.ever_spawned = True

		elif isinstance(obj, Cloud):

			# kill any existing clouds
			cur_cloud = self.tiles[x][y].cloud 
			if cur_cloud is not None:

				if cur_cloud.can_be_replaced_by(obj):
					cur_cloud.kill()
				else:
					return

			self.tiles[x][y].cloud = obj
			self.clouds.append(obj)
			self.event_manager.raise_event(Level.EventOnMakeCloud(x, y , obj))

		elif isinstance(obj, Prop):
			self.add_prop(obj, x, y)
			self.event_manager.raise_event(Level.EventOnMakeProp(x, y , obj))

		else:
			assert(False) # Unknown obj type

Level.add_obj = add_obj_event
		

## Modifications to Advance to activate quick_move using the mostly ignored moves_left attribute

def advance_new(self, orders=None):
	
	can_act = True
	for b in self.buffs:
		if not b.on_attempt_advance():
			can_act = False
			if self.is_player_controlled:
				stun_duration = 1 if not isinstance(self.last_action, StunnedAction) else self.last_action.duration + 1
				self.last_action = StunnedAction(b, stun_duration)
				self.level.requested_action = None
				self.level.combat_log.debug("[Wizard:wizard] is %s" % b.name)

	if can_act:
		# Take an action
		if not self.is_player_controlled:
			action = self.get_ai_action()
		else:
			action = self.level.requested_action
			self.level.requested_action = None
			self.last_action = action

		if action:
			logging.debug("%s will %s" % (self, action))

		if isinstance(action, MoveAction):
			if self.is_player_controlled:
				self.level.combat_log.debug("[Wizard:wizard] takes a step")
			self.level.act_move(self, action.x, action.y)
			if self.quick_move and not self.quick_cast_used:
				self.quick_cast_used = True
				return False
			if self.moves_left > 0:
				self.moves_left -= 1
				return False
		elif isinstance(action, CastAction):
			self.level.act_cast(self, action.spell, action.x, action.y)
			if action.spell.get_stat('quick_cast') and not self.quick_cast_used:
				self.quick_cast_used = True
				return False
		elif isinstance(action, PassAction):
			if self.is_player_controlled:
				self.level.combat_log.debug("[Wizard:wizard] stands still")
			self.level.event_manager.raise_event(EventOnPass(self), self)

	self.try_dismiss_ally()

	return True
	
Unit.advance = advance_new



# import inspect #In case I have to launch and aura damage isn't in the tooltip yet.
# def get_RiftWizard():
# 	for f in inspect.stack()[::-1]:
# 		if "file 'RiftWizard2.py'" in str(f):
# 			return inspect.getmodule(f[0])
# 	return inspect.getmodule(f[0])
# RiftWizard = get_RiftWizard()
# RiftWizard.tooltip_colors['aura_damage'] = Tags.Enchantment.color