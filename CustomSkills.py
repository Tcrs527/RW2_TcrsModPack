import sys

from RareMonsters import BatDragon
sys.path.append('../..')

import Spells
import Upgrades
from Game import *
from Level import *
from Monsters import *
from copy import copy
import math
import copy

from mods.TcrsCustomModpack.SharedClasses import *
from mods.TcrsCustomModpack.CustomSpells import EyedraReincarnation, MetalShard, Improvise

print("Custom Skills Loaded")

class Librarian(Upgrade):
	def on_init(self):
		self.name = "librarian"
		self.tags = [Tags.Word, Tags.Sorcery]
		self.asset = ["TcrsCustomModpack", "Icons", "librarian"]
		self.level = 7
		self.description = ("Whenever you cast a level 6 or greater spell, summon a number of living scrolls of that spell's tags equal to the level of the spell." +
							"\nCan summon: [Fire], [Ice], [Lightning], [Nature], [Arcane], [Dark], [Holy], [Metallic], [Chaos], and [Blood] scrolls.")
		self.owner_triggers[EventOnSpellCast] = self.on_spell_cast
		self.scrolls = ScrollConvertor()
		self.scrolls[Tags.Metallic] = MetalShard,LivingMetalScroll()
		self.scrolls[Tags.Chaos] = Improvise,LivingChaosScroll()
		self.excluded = [Tags.Sorcery, Tags.Enchantment, Tags.Conjuration, Tags.Word, Tags.Dragon]
		
	def make_scrolls(self,tag):
		unit = copy.deepcopy(self.scrolls.get(tag)[1])
		unit.team = self.owner.team
		spell = copy.deepcopy(self.scrolls.get(tag)[0])
		spell.statholder = self.owner
		grant_minion_spell(spell, unit, self.owner, 0)
		self.summon(unit, radius=4, sort_dist=False)
		yield

	def on_spell_cast(self, evt):
		if evt.spell.level < 6:
			return
		#if Tags.Word not in evt.spell.tags:
		#	return
		maintags = copy.copy(evt.spell.tags)
		for exclude in self.excluded:
			if exclude in maintags:
				maintags.remove(exclude)
		for i in range(evt.spell.level):
			if len(maintags) > 1:
				random.shuffle(maintags)
			randtag = maintags[0]
			print(randtag.name)
			self.owner.level.queue_spell(self.make_scrolls(randtag))

class BoneShaping(Upgrade):

	def on_init(self):
		self.name = "Bone Shaping"
		self.tags = [Tags.Blood, Tags.Translocation]
		self.level = 4
		self.asset = ["TcrsCustomModpack", "Icons", "boneshaping"]
		self.owner_triggers[EventOnMoved] = self.on_moved
		self.lastx = 0
		self.lasty = 0

	def on_advance(self):
		self.lastx = self.owner.x
		self.lasty = self.owner.y

	def on_moved(self, evt):
		if not evt.teleport:
			return
		
		self.bonesp = self.owner.get_or_make_spell(Spells.Bonespear)
		self.owner.level.act_cast(self.owner, self.bonesp, self.lastx, self.lasty, pay_costs=False)
		
		newX = self.owner.x + (self.owner.x - self.lastx)
		if newX < 0:
			newX = 0
		if newX >= self.owner.level.height:
			newX = self.owner.level.height -1
		newY = self.owner.y + (self.owner.y - self.lasty)
		if newY < 0:
			newY = 0
		if newY >= self.owner.level.height:
			newY = self.owner.level.height -1
		newPoint = Point(newX, newY)
		self.owner.level.act_cast(self.owner, self.bonesp, newPoint.x, newPoint.y, pay_costs=False)
		
		self.lastx = self.owner.x
		self.lasty = self.owner.y

	def get_description(self):
			return ("Cast bone spear when you teleport, targeting the tile you teleported from, then cast it in front of you mirroring the first spear.")
					
class FromAshes(Upgrade):

	def on_init(self):
		self.name = "From the Ashes"
		self.tags = [Tags.Fire, Tags.Holy, Tags.Conjuration]
		self.level = 5
		self.asset = ["TcrsCustomModpack", "Icons", "Testshape3"] ##TODO fix corners, also probably give it a real name.
		
		self.num_summons = 1
		self.minion_health = Phoenix().max_hp
		self.minion_damage = Phoenix().spells[0].damage
		self.minion_range = Phoenix().spells[0].range
		self.fromashes = 0
		self.threshold = 8
		self.global_triggers[EventOnDeath] = self.on_death
		self.owner_triggers[EventOnUnitAdded] = self.on_unit_added
				
	def get_extra_examine_tooltips(self):
		return [Phoenix()]

	def on_unit_added(self, evt):
		if evt.unit != self.owner:
			return
		self.make_phoenix()
		self.fromashes = 0

	def on_death(self, evt):
		if not (Tags.Fire in evt.unit.tags or Tags.Holy in evt.unit.tags):
			return
		self.fromashes += 1
		self.make_phoenix()


	def make_phoenix(self):
		phoenicians = len([u for u in self.owner.level.units if not are_hostile(self.owner, u) and u.name == "Phoenix"]) ##Fix this idk? Same bug with boss mods as houndlord
		if self.fromashes >= self.threshold and phoenicians < self.get_stat('num_summons'):
			self.fromashes -= self.threshold
			phoenix = Phoenix()
			apply_minion_bonuses(self, phoenix)
			self.summon(phoenix)
			grant_minion_spell(Spells.HolyBlast, phoenix, self.owner, cool_down=2)

	def get_description(self):
		return ("For every [Fire] or [Holy] unit that dies gain an ash charge. When you have at least 8 summon a phoenix.\n"
				"The phoenix has a ranged attack dealing [{minion_damage}_fire:fire] and your heavenly blast on a 2 turn cooldown."
				"The phoenix has [{minion_health}_HP:minion_health], and explodes and reincarnates upon death.\n"
				"You can summon up to [{num_summons}:num_summons] Phoenix. "
				"If you have 8 ash charges upon entering a realm, immediately summon a phoenix.\n"
				"Ash Charges: %d" % self.fromashes).format(**self.fmt_dict())

class Lucky13Buff(Buff):
	def __init__(self, spell): 
		Buff.__init__(self)
		self.spell = spell
	
	def on_init(self):
		self.name = "Symbol of Chaos"
		self.color = Tags.Chaos.color
		self.buff_type = BUFF_TYPE_BLESS
		self.tag_bonuses[Tags.Chaos]['quick_cast'] = 1
		self.owner_triggers[EventOnSpellCast] = self.on_cast
			
	def on_cast(self,evt):
		if Tags.Chaos in evt.spell.tags:
			self.owner.level.queue_spell(self.clear_buffs())
			
	def clear_buffs(self):
		self.owner.remove_buff(self)
		yield

class Lucky13(Upgrade):
	def on_init(self): ##Change to 8 because the 8 sided star of chaos, and also 13 levels of spells is a lot
		self.name = "Symbol of Chaos"
		self.asset = ["TcrsCustomModpack", "Icons", "luckynumber8"]
		self.tags = [Tags.Chaos]
		self.level = 4
		self.lucky13 = 0
		self.targ_num = 8
		self.owner_triggers[EventOnSpellCast] = self.on_spell_cast

	def on_spell_cast(self, evt):
		if Tags.Chaos in evt.spell.tags:
			self.lucky13 += evt.spell.level
		elif self.lucky13 > self.targ_num:
			self.lucky13 = 0
	
	def on_advance(self):
		if self.lucky13 == self.targ_num:
			self.lucky13 = 0
			self.owner.apply_buff(Lucky13Buff(self))
		elif self.lucky13 > self.targ_num:
			self.lucky13 = 0

	def get_description(self):
		return ("If exactly 8 levels of [chaos] spells are cast, gain the Symbol of Chaos. This buff grants quickcast to your next [chaos] spell.\n"
				"[Chaos] Spell Levels Cast: %d\n" % self.lucky13)

class Crescendo(Upgrade):
	def on_init(self):
		self.name = "Crescendo"
		self.asset = ["TcrsCustomModpack", "Icons", "crescendo3"] ##TODO Fix corners
		self.tags = [Tags.Sorcery]
		self.level = 5
		self.base = 1
		self.finale = 5
		self.owner_triggers[EventOnSpellCast] = self.on_spell_cast

	def get_description(self):
		return ("If 5 sorcery spells are cast, each 1 level higher than the last, summon a lamasu.\n"
				"Current Level: %d\n" % self.base +
				"Final Level: %d\n" % self.finale)

	def get_extra_examine_tooltips(self):
		return [Lamasu()]

	def on_spell_cast(self, evt):
		if Tags.Sorcery in evt.spell.tags:
			if self.base == evt.spell.level - 1:
				self.base += 1
			else:
				self.base = evt.spell.level
				self.finale = evt.spell.level + 4
			if self.base == self.finale:
				self.summon(Lamasu())
				

class PsionicBlast(Upgrade): ##This could be an equipment instead, it's kind of awkward as a skill.
	def on_init(self):
		self.name = "Psionic Blast"
		self.asset = ["TcrsCustomModpack", "Icons", "psionic_blast"]
		self.tags = [Tags.Arcane]
		self.level = 4 
		self.range = 5
		self.counter = 0
		self.description = "Every 3 turns while channeling any spell, cast your devour mind on a nearby viable target."

	def can_target(self, target):
		if not are_hostile(self.owner, target):
			return False
		if Tags.Living in target.tags:
			return True

		if self.md_spell.get_stat('spiriteater') and (Tags.Demon in target.tags or Tags.Arcane in target.tags):
			return True

		return False

	def get_targets(self):
		potential_targets = self.owner.level.get_units_in_ball(self.owner, self.get_stat('range'))
		potential_targets = [t for t in potential_targets if self.can_target(t)]
		if potential_targets != []: ##TODO Fix this stupid code - Note I can no longer tell why I thought this was stupid.
			random.shuffle(potential_targets)
			return potential_targets[0]
		return False

	def on_advance(self):
		if self.owner.has_buff(ChannelBuff):
			self.counter += 1
			if self.counter >= 3:
				self.counter = 0
				self.md_spell = self.owner.get_or_make_spell(Spells.MindDevour)
				unit = self.get_targets()
				if unit != False:
					self.owner.level.act_cast(self.owner, self.md_spell, unit.x, unit.y, pay_costs=False)

class BatBreathChiro(BreathWeapon):
	def on_init(self):
		self.name = "Torrent of Bats"
		self.damage = 7
		self.damage_type = Tags.Physical

	def get_description(self):
		return "Breathes a cone of bats dealing %d damage to occupied tiles and summoning bats for 4 turns in empty ones." % self.damage

	def per_square_effect(self, x, y):
		bat = Bat()
		unit = self.caster.level.get_unit_at(x, y)
		if unit:
			self.caster.level.deal_damage(x, y, self.damage, self.damage_type, self)
		else:
			bat.turns_to_death = 4
			self.summon(bat, Point(x, y))

def ChiroDragon():
	dragon = Unit()
	dragon.name = "Chiroptivyern"
	dragon.asset = ["TcrsCustomModpack", "Units", "wyrm_bat"]

	dragon.max_hp = 75
	dragon.burrowing = True
	dragon.buffs.append(RegenBuff(8))
	dragon.resists[Tags.Dark] = 75
	dragon.tags = [Tags.Dragon, Tags.Living, Tags.Dark]
	
	dragon.spells.append(BatBreathChiro())
	dragon.spells.append(SimpleMeleeAttack(8))

	return dragon

class Chiroptyvern(Upgrade):
	def on_init(self):
		self.name = "Chiroptivyern"
		self.asset = ["TcrsCustomModpack", "Icons", "chiroptywvern"]
		self.tags = [Tags.Dragon, Tags.Dark, Tags.Conjuration]
		self.level = 7 ##Seems very strong, level 7? Increase required dark levels?
		
		self.minion_health = ChiroDragon().max_hp
		self.minion_damage = ChiroDragon().spells[1].damage
		self.minion_range = ChiroDragon().spells[0].range
		self.breath_damage = ChiroDragon().spells[0].damage
		self.owner_triggers[EventOnSpellCast] = self.on_cast
		self.dark_spell_evt = 0

	def get_description(self):
		return ("When you cast 5 or more levels of [dark] spells, and then a [dragon] spell, summon a bat wyrm.\n"
				"Current level of [dark] spells: %d\n" % self.dark_spell_evt)

	def get_extra_examine_tooltips(self):
		return [ChiroDragon()]

	def on_cast(self, evt):
		if Tags.Dark in evt.spell.tags:
			self.dark_spell_evt += evt.spell.level
		elif Tags.Dragon in evt.spell.tags and self.dark_spell_evt >= 5:
			drag = ChiroDragon()
			drag.max_hp = self.get_stat('minion_health')
			drag.spells[0].damage = self.get_stat('breath_damage')
			drag.spells[0].range = self.get_stat('minion_range')
			drag.spells[1].damage = self.get_stat('minion_damage')
			self.summon(drag)
			self.dark_spell_evt = 0
		


class Condensation(Upgrade):
	def on_init(self):
		self.name = "Condensation"
		self.tags = [Tags.Ice, Tags.Conjuration]
		self.asset = ["TcrsCustomModpack", "Icons", "condensation"]
		self.level = 6 ##Strong with stormcaller, not amazingly OP on its own.
		
		self.radius = 1
		self.minion_health = 10
		self.minion_damage = 3
		self.minion_range = 3
		self.description = "Each turn, convert blizzard clouds or rain clouds in neighbouring tiles into ice slimes."
		
	def get_extra_examine_tooltips(self):
		return [IceSlime()]

	def on_advance(self):
		for p in self.owner.level.get_points_in_rect(self.owner.x - self.radius, self.owner.y - self.radius, self.owner.x + self.radius, self.owner.y + self.radius):
			tile = self.owner.level.tiles[p.x][p.y]
			if isinstance(tile.cloud, BlizzardCloud) or isinstance(tile.cloud, RainCloud):
				tile.cloud.kill()
				unit = IceSlime()
				apply_minion_bonuses(self, unit)
				self.summon(unit=unit, target=tile)


class AngularGeometry(Upgrade): ##TODO fix this bullshit, it needs work
	def on_init(self):
		self.name = "Sacred Geometry"
		self.tags = [Tags.Holy, Tags.Enchantment]
		self.asset = ["TcrsCustomModpack", "Icons", "sacred_geometry"]
		self.level = 0
		
		self.owner_triggers[EventOnSpellCast] = self.on_cast
		self.damage = 10
		self.description = "For every 4 enchantment spells you cast, create a circle at the center of the 4 points, with its radius being the average distance between them, then deal 10 holy damage to enemy units in the circle, and give allies 1 shield."
		self.min_x = 0
		self.max_x = 0
		self.min_y = 0
		self.max_y = 0
		self.count = 0
		self.points = []
		
	def on_cast(self, evt):
		if not Tags.Enchantment in evt.spell.tags:
			return
		point = Point(evt.x,evt.y)
		self.points.append(point)
		if self.count == 0:
			self.min_x = point.x
			self.max_x = point.x
			self.min_y = point.y
			self.max_y = point.y
		else:
			if point.x > self.max_x: self.max_x = point.x
			elif point.x < self.min_x: self.min_x = point.x
			if point.y > self.max_y: self.max_y = point.y
			elif point.y < self.min_y: self.min_y = point.y
		self.count += 1
		if  self.count >= 4:
			self.count = 0
			x = 0
			y = 0
			for p in self.points:
				print(p)
				x += p.x
				y += p.y
			x = math.ceil(x / 4)
			y = math.ceil(y / 4)
			print(Point(x,y))
			radius = ((self.max_x - self.min_x) + (self.max_y - self.min_y)) // 4
			print(radius)
			points = self.owner.level.get_points_in_ball(x, y, radius)
			#points = self.owner.level.get_points_in_rect(self.min_x,self.min_y,self.max_x,self.max_y)
			for p in points:
				self.owner.level.show_effect(p.x, p.y, Tags.Holy)
				unit = self.owner.level.get_unit_at(p.x,p.y)
				if unit == None: continue
				if self.owner.level.are_hostile(self.owner, unit):
					self.owner.level.deal_damage(unit.x, unit.y, self.get_stat('damage'), Tags.Holy, self)
				else:
					unit.shields += 1
			self.points = []


class Discharge(Upgrade):
	def on_init(self):
		self.name = "Discharge"
		self.tags = [Tags.Lightning]
		self.level = 5
		self.asset = ["TcrsCustomModpack", "Icons", "discharge"]
		
		self.owner_triggers[EventOnSpellCast] = self.on_cast
		self.owner_triggers[EventOnUnitAdded] = self.on_enter_level
		self.num_targets = 1
		self.charges = 0
		self.activated = False
	
	def on_enter_level(self, evt):
		print(evt.unit.name)
		if evt.unit != self.owner:
			return
		self.charges = 0
	
	def on_cast(self,evt):
		if Tags.Lightning not in evt.spell.tags or self.activated:
			return
		self.charges += evt.spell.get_stat('max_charges') - evt.spell.get_stat('cur_charges')
		self.activated = True

	def on_advance(self):
		if self.charges > 0:
			targets = [u for u in self.owner.level.units if self.owner.level.are_hostile(self.owner, u) and not u.resists[Tags.Lightning]==100]
			if targets == []:
				return
			count = self.get_stat('num_targets')
			random.shuffle(targets)
			while targets != [] and count > 0:
				count -= 1
				target = targets.pop(0)
				dmg = self.charges
				dmg = dmg * self.tag_bonuses_pct[Tags.Lightning].get('damage', 0)
				target.deal_damage(self.get_stat('charges'), Tags.Lightning, self)
				self.charges = self.charges - math.ceil(self.charges / 10)
		self.activated = False

	def get_description(self):
		return ("Once a turn when you cast a [lightning] spell, gain charges equal to the difference between the max and current charges.\n" +
				"Each turn deal [lightning] damage to [{num_targets}_enemies:num_targets] equal to your total number of charges, "
				"then lose 10% of your charges rounded up.\n" +
				"Current charge: %d\n" % self.charges).format(**self.fmt_dict())
			
class FrictionBuff(Buff):

	def __init__(self):
		Buff.__init__(self)

	def on_init(self):
		self.buff_type = BUFF_TYPE_BLESS
		self.stack_type = STACK_INTENSITY
		self.color = Tags.Fire.color
		self.name = "Friction"
		self.tag_bonuses[Tags.Fire]['radius'] = 0.25
		self.tag_bonuses[Tags.Fire]['range'] = 0.25
		self.tag_bonuses[Tags.Fire]['damage'] = 3
		self.owner_triggers[EventOnSpellCast] = self.on_cast
		
	def on_cast(self,evt):
		if Tags.Fire in evt.spell.tags:
			self.owner.level.queue_spell(self.clear_buffs())
		
	def clear_buffs(self):
		self.owner.remove_buff(self)
		yield

class Friction(Upgrade):
	def on_init(self):
		self.name = "Friction"
		self.tags = [Tags.Fire, Tags.Translocation]
		self.level = 4
		self.asset = ["TcrsCustomModpack", "Icons", "friction"]
		self.duration = 4
		self.description = ("Gain a stack of friction whenever you move. Gain two stacks for teleporting. Lose all stacks when you cast a [Fire] spell." +
							"Each stack of friction grants [Fire] spells 5 damage, 0.5 radius and 0.5 range. Lasts [{duration}_turns:duration].").format(**self.fmt_dict())
		self.owner_triggers[EventOnMoved] = self.on_moved

	def on_moved(self, evt):
		duration = self.get_stat('duration')
		if not evt.teleport:
			self.owner.apply_buff(FrictionBuff(),duration)
		else:
			self.owner.apply_buff(FrictionBuff(),duration)
			self.owner.apply_buff(FrictionBuff(),duration)

class PoisonousCopy(Upgrade):
	def on_init(self):
		self.name = "Poisonous Doubling"
		self.tags = [Tags.Fire, Tags.Nature]
		self.asset = ["TcrsCustomModpack", "Icons", "poisonous_copy"]
		self.level = 5
		self.owner_triggers[EventOnSpellCast] = self.on_spell_cast
		self.copies = 0

	def get_description(self):
		return ("Whenever you cast a [fire] spell targeting a [poisoned] unit, make a copy of that spell targeting one other unit randomly.\n"
				"Remove [poisoned] from the target. Activates at most 10 times per turn.").format(**self.fmt_dict())

	def on_spell_cast(self, evt):
		if Tags.Fire not in evt.spell.tags:
			return
		unit = self.owner.level.get_unit_at(evt.x, evt.y)
		if not unit:
			return
		b = unit.get_buff(Poison)
		if not b:
			return
		if self.copies > 10: ##If you get in a loop of casting fire spells on poisoned fire immune enemies, break if you reach this point 10 times.
			self.copies = 0
			return False
		
		print(self.copies)
		copy_targets = [u for u in self.owner.level.units if are_hostile(self.owner, u) and u != unit]
		target = random.choice(copy_targets)
		spell = type(evt.spell)()
		self.copies += 1

		unit.remove_buff(Poison)
		if evt.spell.can_copy(target.x, target.y):
			self.owner.level.act_cast(self.owner, evt.spell, target.x, target.y, pay_costs=False)


class IcyVeins(Upgrade):
	def on_init(self):
		self.name = "Icy Veins"
		self.tags = [Tags.Ice, Tags.Blood]
		self.level = 7 #Extremely ridiculously powerful effect, test at level 7 for sure. Super cool imho, Rebalance somehow. Perhaps only allied units? Then reduce threshold?
		self.asset = ["TcrsCustomModpack", "Icons", "icy_veins"]
		self.global_triggers[EventOnDamaged] = self.on_damaged
		self.iceblood = 0
		#if isinstance(s, Spell)
		
	def on_damaged(self, evt):
		print("Source Name:")
		print(evt.source.name)
		print("Source Owner")
		print(evt.source.owner.name)
		if evt.damage_type != Tags.Ice:
			return
		self.iceblood += evt.damage
		#if evt.source == self.owner:
		#	self.iceblood = self.iceblood + evt.damage * 2
				
	def on_advance(self):
		if self.iceblood < 10:
			return
		blood_spells = [s for s in self.owner.spells if Tags.Blood in s.tags]
		while blood_spells != []:
			s = blood_spells.pop(0)
			if (s.level * 10) + s.hp_cost <= self.iceblood:
				if s.range == 0:
					self.cast_spell(s, self.owner.x, self.owner.y)
				elif Tags.Conjuration in s.tags and Tags.Sorcery not in s.tags:
					for p in self.owner.level.get_adjacent_points(Point(self.owner.x,self.owner.y), filter_walkable=True):
						if p != None:
							self.cast_spell(s, p.x, p.y)
							break
				else:
					targets = [u for u in self.owner.level.get_units_in_ball(self.owner, radius=s.range) if are_hostile(u, self.owner)]
					if targets == []: continue
					t = random.choice(targets)
					self.cast_spell(s, t.x, t.y)
			
	def cast_spell(self,spell,x,y):
		if spell.can_cast(x, y):
			self.owner.level.act_cast(spell.caster, spell, x, y, pay_costs=False)
			self.iceblood = 0

	def get_description(self):
		return ("Generate 1 iceblood for every ice damage dealt to a unit. "
				"Each turn automatically cast a viable blood spell on a random target, then lose all iceblood.\n"
				"A spell can be cast for 10 iceblood per the level of the blood spell, plus the hp cost in iceblood.\n"
				"Always attempts to cast your blood spells in order from top to bottom, conjuration spells are cast on a neighbouring tile.\n"
				"Current Iceblood: %d\n" % self.iceblood)

class PuregleamBuff(Buff):

	def __init__(self, skill):
		self.skill = skill
		Buff.__init__(self)

	def on_init(self):
		self.buff_type = BUFF_TYPE_BLESS
		self.stack_type = STACK_DURATION
		self.color = Tags.Holy.color
		self.name = "Puregleam"
		self.dtypes = [Tags.Holy, Tags.Physical]

	def on_advance(self):
		targets = [u for u in self.owner.level.get_units_in_los(self.owner) if are_hostile(self.owner, u)]
		random.shuffle(targets)
		for i in range(self.skill.get_stat('num_targets')):
			dtype = self.dtypes[i%2]
			cur_avail_targets = [t for t in targets if t.resists[dtype] < 100]
			if not cur_avail_targets:
				continue
			target = cur_avail_targets.pop()
			if dtype == Tags.Holy:
				target.apply_buff(BlindBuff(),self.skill.get_stat('duration'))
			elif dtype == Tags.Physical:
				target.apply_buff(Stun(), 1)
			target.deal_damage(self.skill.get_stat('damage'), dtype, self)

			self.owner.level.show_effect(target.x, target.y, dtype, minor=True)
			if len(targets) > 1:
				targets.remove(target)


class HolyMetalLantern(Upgrade):

	def on_init(self):
		self.name = "Puregleam Lantern"
		self.tags = [Tags.Holy, Tags.Metallic]
		self.asset = ["TcrsCustomModpack", "Icons", "puregleam_lantern"]
		self.level = 5
		self.owner_triggers[EventOnSpellCast] = self.on_spell_cast
		self.damage = 1
		self.duration = 5
		self.num_targets = 2

	def get_description(self):
		return ("Whenever you cast a [holy] or [metallic] spell, gain puregleam with duration equal to the spell's level.\n"
				"While you have the buff up to [{num_targets}:num_targets] enemy units in line of sight are either "
				"dealt [{damage}_holy:holy] damage and blinded for [{duration}_turns:duration], or dealt [{damage}_physical:physical] damage and stunned for 1 turn.").format(**self.fmt_dict())

	def on_spell_cast(self, evt):
		if Tags.Holy in evt.spell.tags or Tags.Metallic in evt.spell.tags:
			self.owner.apply_buff(PuregleamBuff(self), evt.spell.level)

def EyeKnight():
	unit = Unit()
	unit.name = "Eye Knight"
	unit.asset =  ["TcrsCustomModpack", "Units", "eye_knight"]
	unit.max_hp = 25
	unit.resists[Tags.Dark] = 100

	unit.spells.append(SimpleMeleeAttack(damage=11, damage_type=Tags.Dark))
	unit.tags = [Tags.Dark, Tags.Eye, Tags.Demon]

	return unit

class NightsightBuff(Buff):
	def __init__(self, skill):
		self.skill = skill
		self.knight = None
		Buff.__init__(self)

	def on_init(self):
		self.buff_type = BUFF_TYPE_BLESS
		self.stack_type = STACK_DURATION
		self.color = Tags.Eye.color
		self.name = "Nightsight"
		self.dtypes = [Tags.Eye, Tags.Dark]

	def make_knight(self):
		self.knight = EyeKnight()
		apply_minion_bonuses(self.skill, self.knight)
		self.summon(self.knight)
		for spell in self.owner.spells: ##TODO teach it one random elemental eye no matter what you have?
			if Tags.Eye in spell.tags:
				grant_minion_spell(type(spell), self.knight, self.owner, cool_down=15)

	def on_applied(self, owner):
		if self.knight == None:
			self.make_knight()

	def on_unapplied(self):
		self.knight.kill()
		self.knight = None

	def on_advance(self):
		if self.knight == None or self.knight.is_alive() == False:
			self.make_knight()
		else:
			self.knight.max_hp += 5
			self.knight.cur_hp += 5
			melee = [s for s in self.knight.spells if s.name == "Melee Attack"][0]
			melee.damage += 2

class NightsightLantern(Upgrade):
	def on_init(self):
		self.name = "Nightsight Lantern" #Darksight? 
		self.tags = [Tags.Dark, Tags.Eye, Tags.Conjuration]
		self.asset = ["TcrsCustomModpack", "Icons", "nightsight_lantern"]
		self.level = 5
		self.owner_triggers[EventOnSpellCast] = self.on_spell_cast
		self.global_triggers[EventOnDeath] = self.on_death

	def get_description(self):
		return ("Whenever you cast a [dark] or [eye] spell, gain Nightsight with duration equal to the spell's level. Eye spells give 4 times their level. \n"
				"While you have the buff summon an Eye Knight until you no longer have the buff. Teach the newly summoned knight your eye spells. \n"
			    "Each turn the Eye Knight gains 5 bonus HP, and 2 melee damage.\n").format(**self.fmt_dict())
	
	def get_extra_examine_tooltips(self):
		return [EyeKnight()]

	def on_death(self, evt):
		buff = self.owner.get_buff(NightsightBuff)
		if buff != None:
			if evt.unit == buff.knight:
				buff.make_knight

	def on_spell_cast(self, evt): ##Wonky interaction with spell queues from bloody orb death shock, probably has to do with act_cast queueing
		if Tags.Dark in evt.spell.tags or Tags.Eye in evt.spell.tags:
			if Tags.Eye in evt.spell.tags:
				self.owner.apply_buff(NightsightBuff(self), evt.spell.level * 4)
			else:
				self.owner.apply_buff(NightsightBuff(self), evt.spell.level)

class ContractFromBuff(Buff):
	def __init__(self, skill):
		self.skill = skill
		Buff.__init__(self)

	def on_init(self):
		self.buff_type = BUFF_TYPE_BLESS
		self.stack_type = STACK_REPLACE
		self.color = Tags.Dark.color
		self.name = "Demonic Contract"
		self.dtypes = [Tags.Dark, Tags.Chaos]
		self.tag_bonuses[Tags.Dark]['quick_cast'] = 1
		self.tag_bonuses[Tags.Chaos]['quick_cast'] = 1
		self.owner_triggers[EventOnSpellCast] = self.on_cast

	def on_cast(self,evt):
		if Tags.Dark in evt.spell.tags or Tags.Chaos in evt.spell.tags:
			self.owner.deal_damage(self.skill.get_stat('damage'), Tags.Holy, self)
		else:
			self.owner.deal_damage(2, Tags.Holy, self)

class ContractFromBelow(Upgrade):
	def on_init(self):
		self.name = "Contract from Below"
		self.tags = [Tags.Dark, Tags.Chaos]
		self.asset = ["TcrsCustomModpack", "Icons", "contract_from_below"]
		self.description =	("In each realm, after you summon 5 uniquely named demons, gain Demonic Contract.\n Demonic contract gives your [dark] and [chaos] spells quickcast," + "and deals 10 [holy] damage to you per [dark] or [chaos] spell cast. All other spells deal 2 damage to you.")
		self.level = 7 ##This is far weaker now that quickcast has been toned down. I can probably nerf the self damage.
		self.damage = 10
		self.demons = {}
		self.global_triggers[EventOnUnitAdded] = self.on_unit_added
	

	def on_unit_added(self, evt):
		if evt.unit == self.owner:
			self.demons = {}
		else:
			print(evt.unit.name)
			if not self.owner.level.are_hostile(self.owner, evt.unit) and Tags.Demon in evt.unit.tags:
				self.demons[evt.unit.name] = True
				if len(self.demons.keys()) >= 5:
					print(self.demons.keys())
					self.owner.apply_buff(ContractFromBuff(self))
					

class MageArmorBuff(Buff):
	def __init__(self, resist_tags):
		Buff.__init__(self)
		self.name = "Enchanter's Armor"
		self.buff_type = BUFF_TYPE_BLESS
		self.resist_tags = resist_tags
		
		for tag in self.resist_tags:
			self.resists[tag] = resist_tags[tag]

class MageArmor(Upgrade):
	def on_init(self):
		self.name = "Enchanter's Armor"
		self.tags = [Tags.Enchantment]
		self.asset = ["TcrsCustomModpack", "Icons", "magearmor"] #Variation of Dwarven Chainmail by K.Hoops
		self.level = 5
		self.global_triggers[EventOnUnitAdded] = self.on_unit_added
		self.duration = 10
		self.description = ("Upon entering a realm, gain 25%  resistance to each damage type for each spell tags in each spell you know for [{duration}_turns:duration].\n" +
							"[Fire] grants [Fire] resistance, then repeat for all tags with corresponding damage types." +
							"[Nature] tags grant [Poison] resistance and [Metallic] tags [Physical] resistance.").format(**self.fmt_dict())

	def on_unit_added(self, evt):
		if evt.unit == self.owner:
			restags = {Tags.Fire:0,Tags.Ice:0,Tags.Lightning:0,Tags.Arcane:0,Tags.Dark:0,Tags.Holy:0,Tags.Poison:0,Tags.Physical:0}
			spells = self.owner.spells
			for spell in spells:
				#if Tags.Enchantment not in spell.tags: ##Used to be limited to enchanting spells, does this matter?
				#	continue
				for t in spell.tags:
					if t == Tags.Nature:t = Tags.Poison
					if t == Tags.Metallic:t = Tags.Physical
					if t in restags:
						restags[t] += 25
						
			self.owner.apply_buff(MageArmorBuff(restags),self.get_stat('duration'))

class AcceleratorBuff(Buff):
	def on_init(self):
		self.buff_type = BUFF_TYPE_BLESS
		self.stack_type = STACK_REPLACE
		self.color = Tags.Enchantment.color
		self.name = "Accelerator"
		self.tag_bonuses[Tags.Enchantment]['quick_cast'] = 1
		self.owner_triggers[EventOnSpellCast] = self.on_cast
		
	def on_cast(self,evt):
		if Tags.Enchantment in evt.spell.tags:
			self.owner.level.queue_spell(self.clear_buffs())
			
	def clear_buffs(self):
		self.owner.remove_buff(self)
		yield

class Accelerator(Upgrade):
	def on_init(self):
		self.name = "Accelerator"
		self.tags = [Tags.Enchantment]
		self.asset = ["TcrsCustomModpack", "Icons", "accelerator"]
		self.description = "Every 100 damage dealt with [enchantment] spells, grant yourself the Accelerator buff for 5 turns. The buff gives quickcast to your next enchantment spell."
		self.level = 6
		self.global_triggers[EventOnDamaged] = self.on_damage

		self.threshold = 100
		self.charges = 0
		self.duration = 5 ##Todo tooltip turns 

	def on_damage(self, evt):
		if not isinstance(evt.source, Spell):
			return
		if evt.source.caster != self.owner:
			return
		if Tags.Enchantment not in evt.source.tags:
			return

		self.charges += evt.damage
		if self.charges >= self.threshold:
			self.charges -= self.threshold
			self.owner.apply_buff(AcceleratorBuff(),self.get_stat('duration'))


class WeaverOfElements(Upgrade):
	def on_init(self):
		self.name = "Weave the Elements"
		self.tags = [Tags.Fire, Tags.Ice, Tags.Lightning]
		self.asset = ["TcrsCustomModpack", "Icons", "weaver_of_elements"]
		self.description = ("For every 3 [Fire], [Ice], or [Lightning] spells you cast, deal damage in a line between each point and the other two points.\n" +
							"Deal [fire] damage if any of the spells had the [fire] tag, then repeat for [Ice] and [Lightning].\n"
							"Does not hurt you. Does work with free spells.")
		self.level = 5 ##Change this to every 3 spells cast, and make a triangle between the 3 points
		
		self.owner_triggers[EventOnSpellCast] = self.on_cast
		self.damage = 5
		self.points = []
		self.spell_tags = []
	
	def on_cast(self, evt):
		if Tags.Fire in evt.spell.tags or Tags.Ice in evt.spell.tags or Tags.Lightning in evt.spell.tags:
			p = Point(evt.x, evt.y)
			self.points.append(p)
			for tag in evt.spell.tags:
				if tag not in self.spell_tags and tag in self.tags:
					self.spell_tags.append(tag)
			print(self.points)
			print(self.spell_tags)
			print(len(self.points))
			wizard_p = Point(self.owner.x, self.owner.y)
			if len(self.points) >= 3:
				if self.spell_tags == []:
					self.points = []
					return
				for p in self.points:
					target_points = copy.deepcopy(self.points)
					target_points.remove(p)
					for tp in target_points:
						line = self.owner.level.get_points_in_line(start=p, end=tp, find_clear=False)
						for point in line:
							if not point == wizard_p:
								for tag in self.spell_tags:
									self.owner.level.deal_damage(point.x, point.y, self.get_stat('damage'), tag, self)
				self.points = []
				self.spell_tags = []

class WeaverOfOccultism(Upgrade):
	def on_init(self):
		self.name = "Weave the Occult"
		self.tags = [Tags.Arcane, Tags.Dark, Tags.Holy, Tags.Blood]
		self.asset = ["TcrsCustomModpack", "Icons", "weaver_of_occult"]
		self.level = 6
		
		self.owner_triggers[EventOnSpellCast] = self.on_cast
		self.points = []
		self.spell_tags = []
		self.ghostdict = {Tags.Arcane:GhostVoid(), Tags.Dark:DeathGhost(), Tags.Holy:HolyGhost(), Tags.Blood:Bloodghast()}
		
		self.minion_health = 4
		self.minion_damage = 2
		self.minion_duration = 5
	
	def get_description(self):
		return ("For every 3 spells you cast, summon ghosts at the target tile of each spell. Ghosts last [{minion_duration}_turns:minion_duration] turns.\n"
				"If the [arcane] tag was in any spell, summon a void ghost, then repeat for [dark], [holy], and [blood].\n"
				"Does not work with free spells.").format(**self.fmt_dict())

	def on_cast(self, evt): ##TODO standardize this to only work with specific tags?
		if not evt.pay_costs:
			return
		p = Point(evt.x, evt.y)
		self.points.append(p)
		for tag in evt.spell.tags:
			if tag not in self.spell_tags and tag in self.tags:
				self.spell_tags.append(tag)
		if len(self.points) >= 3: ##Casts on every second spell after the first time, for obvious reasons. Need to increment elsewhere?>
			if self.spell_tags == []:
				return
			for p in self.points:
				for tag in self.spell_tags:
					unit = copy.deepcopy(self.ghostdict[tag])
					unit.max_hp = self.get_stat('minion_health')
					apply_minion_bonuses(self, unit)
					unit.turns_to_death = self.get_stat('minion_duration')
					self.owner.level.summon(self.owner, unit, p)
			self.points = []
			self.spell_tags = []

	def get_extra_examine_tooltips(self):
		return [GhostVoid(), DeathGhost(), HolyGhost(), Bloodghast()]


def MaterialSlime():
	unit = Unit()
	unit.name = "Materiel Slime"
	unit.asset = ["TcrsCustomModpack", "Units", "matslime_n"]
	unit.description = "A slime of non-descript features"
	unit.max_hp = 20
	unit.buffs.append(SlimeBuff(spawner=GreenSlime))
	unit.spells.append(SimpleMeleeAttack(5))
	unit.tags = [Tags.Slime]
	unit.resists[Tags.Poison] = 100
	return unit

class WeaverOfMaterialism(Upgrade):
	def on_init(self):
		self.name = "Weave the Material"
		self.tags = [Tags.Nature, Tags.Dragon, Tags.Metallic]
		self.asset = ["TcrsCustomModpack", "Icons", "weaver_of_material"]
		self.description = ("For every 3 spells you cast, summon a slime at the third spell's target.\n" +
							"The slime is a combination of the tags used: if the [nature] tag was in any spell the slime gains poisonous attacks, then repeat "
							"for [Dragon] and a breath attack, and [Metallic] and melee retaliation damage. Newly split slimes are normal green slimes.\n"
							"Does not work with free spells.").format(**self.fmt_dict())
		self.level = 7 ##Change this to every 3 spells cast
		self.owner_triggers[EventOnSpellCast] = self.on_cast
		self.points = []
		self.spell_tags = []
		
		self.minion_health = 15
		self.minion_damage = 5
		self.minion_duration = 25
	
	def on_cast(self, evt):
		if evt.spell.pay_costs == False:
			return
		p = Point(evt.x, evt.y)
		self.points.append(p)
		for tag in evt.spell.tags:
			if tag not in self.spell_tags and tag in self.tags:
				self.spell_tags.append(tag)
		if len(self.points) >= 3:
			if self.spell_tags == []:
				return
			unit = self.get_slime(self.spell_tags)
			apply_minion_bonuses(self, unit)
			self.owner.level.summon(self.owner, unit, self.points[-1]) ##Make it summon at midpoint later
			self.spell_tags = []
			self.points = []

	def get_slime(self, tags):
		spell_tags = tags
		unit = MaterialSlime()

		nature = False
		if Tags.Nature in spell_tags:
			nature = True
		dragon = False
		if Tags.Dragon in spell_tags:
			dragon = True
		metal = False
		if Tags.Metallic in spell_tags:
			metal = True
			
		if nature:
			unit.tags.append(Tags.Nature)
			unit.buffs.append(MushboomBuff(Poison, 12))
			unit.asset = ["TcrsCustomModpack", "Units", "matslime_n"]
			unit.name = "Slimeshroom"
		if dragon:
			unit.tags.append(Tags.Dragon)
			unit.flying = True
			unit.asset = ["TcrsCustomModpack", "Units", "matslime_r"]
			unit.name = "Slimedrake"
			poison_breath = FireBreath()
			poison_breath.damage_type = Tags.Poison
			poison_breath.name = "Poison Breath"
			unit.spells.append(poison_breath)
		if metal:
			unit.tags.append(Tags.Metallic)
			unit.buffs.append(Thorns(6, Tags.Physical))
			unit.asset = ["TcrsCustomModpack", "Units", "matslime_m"]
			unit.name = "Slimespike"

		if nature and dragon:
			if metal:
				unit.asset = ["TcrsCustomModpack", "Units", "matslime_nrm"]
				unit.anme = "Spikeshroom Slimedrake"
			else:
				unit.asset = ["TcrsCustomModpack", "Units", "matslime_nr"]
				unit.name = "Slimeshroom Drake"
		elif nature and metal:
			unit.asset = ["TcrsCustomModpack", "Units", "matslime_nm"]
			unit.name = "Slimespike Shroom"
		elif dragon and metal:
			unit.asset = ["TcrsCustomModpack", "Units", "matslime_rm"]
			unit.name = "Slimespike Drake"

		return unit

	def get_extra_examine_tooltips(self):
		slime = MaterialSlime()
		slime.name = "Spikeshroom Slimedrake"
		slime.asset = ["TcrsCustomModpack", "Units", "matslime_nrm"]
		return [slime]


class Scrapheap(Upgrade):
	def on_init(self):
		self.name = "Scrapheap"
		self.tags = [Tags.Metallic, Tags.Conjuration]
		self.asset =  ["TcrsCustomModpack", "Icons", "scrapheap"]
		self.description = "Each 10 turns summon a scrap golem. For each construct or metallic unit that died during those 10 turns, give it 7 health, or 4 damage."
		self.level = 5 ##Directly comparable to boneguard.
		self.global_triggers[EventOnDeath] = self.on_death
		self.scrap = 0
		self.counter = 0
		self.minion_health = 25
		self.minion_damage = 8
		
	def on_death(self, evt):
		if not (Tags.Construct in evt.unit.tags or Tags.Metallic in evt.unit.tags):
			return
		self.scrap += 1
		
	def on_advance(self):
		self.counter += 1
		if self.counter >= 10: 
			unit = Golem()
			unit.name = "Scrap Golem"
			unit.asset = ["TcrsCustomModpack", "Units", "golem_scrap"+str(random.randint(1,6))]
			for i in range(self.scrap + 1):
				r = random.random()
				if r < 0.5:
					unit.max_hp += 7
				else:
					unit.spells[0].damage += 4
			apply_minion_bonuses(self, unit)
			self.summon(unit)
			self.counter -= 5
			self.scrap = 0

	def get_extra_examine_tooltips(self):
		return [Golem()]

class ArclightEagle(Upgrade): ##Quickcast nerfed, does this get changed to 2 spells?
	def on_init(self):
		self.name = "Arclight Eagle" ##Obviously inspired by Arclight Phoenix
		self.tags = [Tags.Lightning, Tags.Conjuration]
		self.asset = ["TcrsCustomModpack", "Icons", "arclight_eagle"]
		self.description = "On any turn you cast at least 3 spells, one of which is [lightning], summon an eagle. The eagle inherits upgrades from your Flock of Eagles spell."
		self.level = 5
		self.owner_triggers[EventOnSpellCast] = self.on_cast
		self.spells_cast = 0
		self.lightning = False


	def on_cast(self, evt):
		if Tags.Lightning in evt.spell.tags:
			self.lightning = True
		self.spells_cast += 1

	def on_advance(self):
		if self.spells_cast >= 3 and self.lightning == True:
			s = self.owner.get_or_make_spell(FlockOfEaglesSpell)
			eagle = s.make_eagle()
			self.summon(eagle)
		self.spells_cast = 0
		self.lightning = False

class Arithmetic(Buff):
	def __init__(self, skill):
		self.skill = skill
		Buff.__init__(self)
		
	def on_init(self):
		self.buff_type = BUFF_TYPE_BLESS
		self.stack_type	= STACK_NONE
		self.name = "Arithmagics"
		self.color = Tags.Sorcery.color
		#self.asset = ['status', 'stun']
		self.description = "Solve for 0. Math is fun."
		self.owner_triggers[EventOnSpellCast] = self.on_cast
		self.result = 0

	def on_applied(self, owner):
		self.result = random.randint(1, self.skill.damage)
		self.name = "Arithmagics: " + str(self.result)

	def on_cast(self, evt):
		if Tags.Sorcery in evt.spell.tags:
			self.result -= evt.spell.level
		elif Tags.Enchantment in evt.spell.tags:
			self.result = math.ceil(self.result / evt.spell.level)
			
		if self.result == 0:
			self.name = "Arithmagics"
			units = [u for u in self.owner.level.units if u != self.owner]
			for u in units:
				self.owner.level.deal_damage(u.x, u.y, self.skill.damage, Tags.Poison, self)
			if units != []: ##So you can't scale this between realms like a tryhard. needs to check for enemies though.
				self.skill.damage += 1
			self.owner.remove_buff(self)
		elif self.result < 0:
			self.owner.remove_buff(self)
		else:
			self.name = "Arithmagics: " + str(self.result)

class Mathemagics(Upgrade):
	def on_init(self):
		self.name = "Mathemagics Class "
		self.asset = ["TcrsCustomModpack", "Icons", "mathemagics"]
		self.tags = [Tags.Sorcery, Tags.Enchantment]
		self.level = 7
		self.damage = 13

	def on_advance(self):
		if not self.owner.has_buff(Arithmetic):
			print(self)
			#difficulty = self.owner.level.gen_params.difficulty
			self.owner.apply_buff(Arithmetic(self))

	def get_description(self):
		return ("Each turn gain the Arithmagics buff if you don't have it. The buff has a value between 1 and {damage}, " +
				"which when reduced to 0 exactly deals [{damage}:poison] poison damage to all units except the Wizard, then permanently gains 1 damage.\n" + 
				"Sorceries subtract their level from the integer. Enchantment spells divide the integer by the spell's level, rounding up.").format(**self.fmt_dict())


class QueenOfTorment(Upgrade):
	def on_init(self):
		self.name = "Queen of Torment" ##Based on Prince of Ruin. There's no "Torment" Tag, but it will be a placeholder name for poison arcane ice damage together.
		self.tags = [Tags.Nature, Tags.Arcane, Tags.Ice]
		self.asset = ["TcrsCustomModpack", "Icons", "queen_of_torment"]
		self.level = 5
		self.duration = 2
		self.global_triggers[EventOnDeath] = self.on_death #Ice -> Fear, Poison -> Freeze, Arcane -> Poison (Acidified? Could be more interesting)
		self.radius = 5
		
	def get_description(self):
		return ("When an enemy dies to [Ice] damage apply Fear to an enemy within 5 tiles."
				" Repeat for [Poison] damage with the Frozen debuff, and [Arcane] damage with Poisoned plus Acidified debuffs.\n"
				"Fear lasts [{duration}_turns:duration]. Freeze lasts 2 extra turn, Poisoned lasts 4 extra turns, Acidify lasts forever.").format(**self.fmt_dict())

	def on_death(self, evt):
		if not are_hostile(evt.unit, self.owner):
			return
		damage_event = evt.damage_event
		if damage_event and damage_event.damage_type in [Tags.Poison, Tags.Arcane, Tags.Ice]:
			self.owner.level.queue_spell(self.trigger(evt))

	def trigger(self, evt):
		candidates = [u for u in self.owner.level.get_units_in_ball(evt.unit, self.radius) if are_hostile(self.owner, u)]
		if candidates:
			target = random.choice(candidates)
			duration = self.get_stat('duration')
			if evt.damage_event.damage_type == Tags.Ice:
				buff = Fear()
			elif evt.damage_event.damage_type == Tags.Poison:
				buff = FrozenBuff()
				duration += 2
			elif evt.damage_event.damage_type == Tags.Arcane: ##I think this was escaping without finding a damage type, changed to else?
				target.apply_buff(Acidified())
				buff = Poison()
				duration += 4
			target.apply_buff(buff, duration)
		yield


class CloudcoverBuff(Buff):
	def __init__(self, tag):
		self.tag = tag

		Buff.__init__(self)
		self.resists[tag] = 75

	def on_init(self):
		self.name = "Cloudy Covering"
		self.buff_type = BUFF_TYPE_BLESS
		self.stack_type	= STACK_NONE
		self.color = Tags.Enchantment.color
		self.description = "Resistant to the cloud damage type."
		self.resists = {}

class Cloudcover(Upgrade):
	def on_init(self):
		self.name = "Cloud Cover"
		self.tags = [Tags.Enchantment]
		self.asset = ["TcrsCustomModpack", "Icons", "cloudcover"]
		self.level = 5 ##Tentative level 5-6 this is incredibly good with stormcaller, this is very okay with everything else though.
		self.description = "When you end your turn in a cloud, gain 75 resistance to that cloud's damage type for 1 turn. Applies to: Blizzards, Thunderstorms, Poison Clouds, and Fire Clouds."
		self.duration = 1
		self.cloud_dict = {BlizzardCloud:Tags.Ice, StormCloud:Tags.Lightning, PoisonCloud:Tags.Poison, FireCloud:Tags.Fire, RainCloud:Tags.Ice}

	def on_advance(self):
		cloud = self.owner.level.tiles[self.owner.x][self.owner.y].cloud
		if cloud:
			c_type = type(cloud)
			tag = self.cloud_dict[c_type]
			if c_type in self.cloud_dict:
				duration = self.get_stat('duration')
				self.owner.apply_buff(CloudcoverBuff(tag), duration)


class EyeSpellTrigger(Upgrade):
	def on_init(self):
		self.name = "Eye of Providence"
		self.level = 5
		self.tags = [Tags.Eye]
		self.asset = ["TcrsCustomModpack", "Icons", "eye_of_providence"]
		self.description = "When you cast a holy spell, advance your eye spell buffs by one turn."
		self.owner_triggers[EventOnSpellCast] = self.on_cast
		
	def on_cast(self, evt):
		if Tags.Holy not in evt.spell.tags:
			return
		eyebuffs = []
		for b in self.owner.buffs:
			if isinstance(b, (FireEyeBuff, IceEyeBuff, LightningEyeBuff, RageEyeBuff)):
				eyebuffs.append(b)
		if eyebuffs == []:
			return
		for b in eyebuffs:
			b.cooldown -= 1
			if b.cooldown <= 0:
				b.cooldown = b.freq
				possible_targets = self.owner.level.units
				possible_targets = [t for t in possible_targets if self.owner.level.are_hostile(t, self.owner)]
				possible_targets = [t for t in possible_targets if self.owner.level.can_see(t.x, t.y, self.owner.x, self.owner.y)]

				if possible_targets:
					target = random.choice(possible_targets)
					self.owner.level.queue_spell(b.shoot(Point(target.x, target.y)))
					b.cooldown = b.freq


class EyeBuffExtender(Upgrade): ##Dummied out, can't figure out how to get it going.
	def on_init(self):
		self.name = "Enduring Eye"
		self.level = 0
		self.description = "When you cast an eye buff, if you already have it, distribute its remaining duration to your other eye buffs."
		self.tags = [Tags.Eye]
		self.tag_bonuses[Tags.Eye]['shot_cooldown'] = -1
		self.eyedict = {EyeOfFireSpell:FireEyeBuff, EyeOfIceSpell:IceEyeBuff, EyeOfLightningSpell:LightningEyeBuff, EyeOfRageSpell:RageEyeBuff}

	def rename_to_on_cast(self, evt):
		spell = type(evt.spell)
		print(spell)
		#print(self.eyedict.keys())
		if not spell in self.eyedict: ##Incredibly poorly hardcoded spell, cannot figure out how isinstance works with ElementalEyeBuff and its subclasses.
			print("Test")
			return
		print("Getting buff")
		buff = self.owner.get_buff(self.eyedict[spell])
		other_eye_buffs = []
		print("Used dictionary to find buff")
		for b in self.owner.buffs:
			if isinstance(b, (FireEyeBuff, IceEyeBuff, LightningEyeBuff, RageEyeBuff)) and not isinstance(type(b), type(buff)):
				other_eye_buffs.append(b)
		if other_eye_buffs == []:
			return
		print("Adding turns part")
		turns = buff.turns_left // len(other_eye_buffs)
		for b in other_eye_buffs:
			b.turns_left += turns

class Overheal(Upgrade):
	def on_init(self):
		self.name = "Overflowing Vitality"
		self.level = 6
		self.tags = [Tags.Nature, Tags.Conjuration]
		self.asset = ["TcrsCustomModpack", "Icons", "overheal"]
		self.global_triggers[EventOnHealed] = self.on_heal
		self.total = 0
		self.minion_health = 76
		self.minion_damage = 8

	def get_description(self):
		return ("Whenever a unit heals, gain Vitality stacks equal to the amount of missing life healed.\n When Vitality is greater than 75, "
				"consume 75 of it to summon a Giant Satyr.").format(**self.fmt_dict())

	def get_extra_examine_tooltips(self):
		return [SatyrGiant()]

	def on_heal(self, evt):
		#for s in self.owner.spells:
		#	print(s)
		if not evt.source:
			return
		if not hasattr(evt.source, 'tags'):
			return
		heal = evt.heal
		self.total -= heal
		print(self.total)
		if self.total >= 75:
			unit = SatyrGiant()
			apply_minion_bonuses(self, unit)
			self.summon(unit)
			self.total -= 75

class WalkTheOrb(Upgrade): ##This might be a better equipment than skill. Very very niche.
	def on_init(self):
		self.name = "Walk the Orb"
		self.level = 6
		self.tags = [Tags.Orb]
		self.description = ("When you use an orb spell to orb walk, do 50 damage to one random enemy for each different tag in orb spells you know.\n"
							" E.g. converts [Ice] to [Ice] damage, but also [Metallic] to [Physical] damage, and [Blood] to [Dark] damage.").format(**self.fmt_dict())
		self.owner_triggers[EventOnSpellCast] = self.on_cast
		self.tagconv = TagToDmgTagConvertor()
		self.damage = 50
		
	def on_cast(self, evt):
		if Tags.Orb not in evt.spell.tags:
			return
		if not ( evt.spell.get_stat('orb_walk') and evt.spell.get_orb(evt.x, evt.y) ):
			return
		print("Orb Walking Event")
		orb_tags = []
		for s in self.owner.spells:
			for tag in s.tags:
				if tag not in orb_tags:
					orb_tags.append(tag)
		print(orb_tags)
		for tag in orb_tags:
			if tag in self.tagconv:
				dmg_tag = self.tagconv[tag]
				targets = [u for u in self.owner.level.units if self.owner.level.are_hostile(self.owner, u)]
				if targets != []:
					targ = random.choice(targets)
					self.owner.level.deal_damage(targ.x, targ.y, self.damage, dmg_tag, self)
					


class RimeorbDamageBuff(DamageAuraBuff):
	def __init__(self, skill):
		self.skill = skill
		DamageAuraBuff.__init__(self, damage=self.skill.aura_damage, radius=self.skill.get_stat('radius'), damage_type=[Tags.Ice], friendly_fire=False)
		self.name = "Rimeorb Aura"

	def on_init(self):
		self.buff_type = BUFF_TYPE_BLESS
		self.stack_type = STACK_DURATION
		self.color = Tags.Ice.color
		self.name = "Rimeorb Aura"
		
class RimeorbMainBuff(Buff):
	def __init__(self, skill):
		self.skill = skill
		Buff.__init__(self)

	def on_init(self):
		self.buff_type = BUFF_TYPE_BLESS
		self.stack_type = STACK_DURATION
		self.color = Tags.Ice.color
		self.name = "Rimeorb Aura"
		
	def on_advance(self):
		if not self.owner.has_buff(RimeorbDamageBuff):
			buff = RimeorbDamageBuff(self.skill)
			buff.source = self
			self.owner.apply_buff(buff, 20)
		orbs = [t for t in self.owner.level.units if not self.owner.level.are_hostile(t, self.owner) and t.name[-4:] == " Orb" and not t.has_buff(RimeorbDamageBuff)]
		if orbs == []:
			return
		o = random.choice(orbs)
		buff = RimeorbDamageBuff(self.skill)
		buff.source = self
		o.apply_buff(buff, o.turns_to_death)
			
	def on_unapplied(self):
		print("Unapply")
		self.owner.remove_buffs(RimeorbDamageBuff)
		orbs = [t for t in self.owner.level.units if not self.owner.level.are_hostile(t, self.owner) and t.name[-4:] == " Orb" and t.has_buff(RimeorbDamageBuff)]
		if orbs == []:
			return
		print(orbs)
		for o in orbs:
			o.remove_buffs(RimeorbDamageBuff)

class RimeorbLantern(Upgrade):
	def on_init(self):
		self.name = "Rimeorb Lantern"
		self.tags = [Tags.Ice, Tags.Orb, Tags.Enchantment]
		self.asset = ["TcrsCustomModpack", "Icons", "rimeorb_lantern"]
		self.level = 4 ##Aiming for level 4 or 5. Scales extremely poorly at present. Wouldn't mind a source of aura damage somewhere.
		self.radius = 6
		self.aura_damage = 2
		self.owner_triggers[EventOnSpellCast] = self.on_spell_cast

	def get_description(self):
		return ("Whenever you cast an [Ice] or [Orb] spell, gain Rimeorb Aura with duration equal to the spell's level. Orb spells give 3 times their level. \n"
				"Rimeorb Aura grants you a [{radius}_tile:radius] ice damage aura dealing 2 damage to enemies each turn. Each turn you also grant one orb the same aura. "
				"Orbs retain the aura until the buff ends").format(**self.fmt_dict())

	def on_spell_cast(self, evt):
		if Tags.Ice in evt.spell.tags or Tags.Orb in evt.spell.tags:
			buff = RimeorbMainBuff(self)
			buff.source = self
			if Tags.Orb in evt.spell.tags:
				self.owner.apply_buff(buff, evt.spell.level * 3)
			else:
				self.owner.apply_buff(buff, evt.spell.level)
				
class RiotscaleBreath(BreathWeapon):
	def on_init(self):
		self.name = "Chaos Breath"
		self.damage = 15
		self.range = 5

	def per_square_effect(self, x, y):
		damage_type = random.choice([Tags.Fire, Tags.Lightning, Tags.Physical])
		self.caster.level.deal_damage(x, y, self.damage, damage_type, self)

class ChaosScaleBuff(Buff):
	def __init__(self, skill):
		self.skill = skill
		self.breath_damage = skill.get_stat('breath_damage')
		self.range = 4
		self.cooldown = 2
		Buff.__init__(self)
		
	def on_init(self):
		self.name = "Riotscale Rage"
		self.tags = [Tags.Dragon, Tags.Chaos]
		self.color = Tags.Dragon.color
		self.stack_type = STACK_DURATION
		self.buff_type = BUFF_TYPE_BLESS
		#self.asset = ["TcrsCustomModpack", "Icons", "nightsight_lantern"]

	def on_advance(self):
		self.cooldown -= 1
		if self.cooldown > 0:
			return
		targets = [t for t in self.owner.level.get_units_in_ball(self.owner, self.range) if are_hostile(self.owner, t) and self.owner.level.can_see(t.x, t.y, self.owner.x, self.owner.y)]
		self.range += 1
		if targets == []:
			return
		breath = self.owner.get_or_make_spell(RiotscaleBreath)
		breath.range = self.range
		breath.source = self
		breath.damage = self.breath_damage
		unit = random.choice(targets)
		self.owner.level.act_cast(self.owner, breath, unit.x, unit.y, pay_costs=False)
		self.range = 4
		self.cooldown = 2
		
class ChaosScaleLantern(Upgrade): ##TODO This might be teaching you spells based on last cast, see if it's this or duergar helm.
	def on_init(self):
		self.name = "Riotscale Lantern"
		self.tags = [Tags.Dragon, Tags.Chaos]
		self.asset = ["TcrsCustomModpack", "Icons", "riotscale_lantern"]
		self.level = 5
		self.owner_triggers[EventOnSpellCast] = self.on_spell_cast
		self.breath_damage = 15
		self.range = 4

	def get_description(self):
		return ("Whenever you cast a [Dragon] or [Chaos] spell, gain Riotscale Rage with duration equal to the spell's level. Dragon spells give 3 times their level.\n"
				"The buff gives you an automatic breath attack with a 1 turn cooldown.\n"
				" The breath attack has a range of 4 and deals [15:breath_damage] [Physical], [Fire], or [Lightning] damage randomly."
				" Each turn the breath gains 1 range, but when it activates its range resets to 4.").format(**self.fmt_dict())

	def on_spell_cast(self, evt):
		if Tags.Dragon in evt.spell.tags or Tags.Chaos in evt.spell.tags:
			buff = ChaosScaleBuff(self)
			if Tags.Dragon in evt.spell.tags:
				self.owner.apply_buff(buff, evt.spell.level * 3)
			else:
				self.owner.apply_buff(buff, evt.spell.level)


class AuraReading(Upgrade):
	def on_init(self):
		self.name = "Aura Reading"
		self.level = 5
		self.tags = [Tags.Arcane, Tags.Dark, Tags.Enchantment] ##TODO implement modifiable aura damage on inferno engines.
		self.description = ("When an aura is given to an allied unit, that unit also gains a 2 damage physical aura with the same size and duration.\n" +
							"When a unit's aura ends, it spawns a Purple Pachyderm for each 50 damage dealt by the aura.")
		self.asset = ["TcrsCustomModpack", "Icons", "aura_reading"]
		
		self.global_triggers[EventOnBuffApply] = self.buff_applied
		self.global_triggers[EventOnBuffRemove] = self.buff_removed
		self.global_triggers[EventOnDeath] = self.on_death
		
		self.aura = 0
		self.threshold = 50
		self.minion_health = 55
		self.minion_damage = 12

	def on_death(self, evt):
		if not evt.unit.has_buff(DamageAuraBuff):
			return
		buff = evt.unit.get_buff(DamageAuraBuff)
		self.spawn_pachyderm(buff.damage_dealt)

	def buff_applied(self, evt):
		if isinstance(evt.buff, DamageAuraBuff) and evt.buff.name != "Physical Aura": ##TODO check to see if enemy auras grant them a version of this.
			print("Applying Buff")
			buff = DamageAuraBuff(damage=2, radius=evt.buff.radius, damage_type=[Tags.Physical], friendly_fire=False)
			buff.stack_type = STACK_REPLACE
			buff.color = Tags.Physical.color
			buff.name = "Physical Aura"
			buff.source = self
			evt.unit.apply_buff(buff, evt.buff.turns_left)
			print("Buff Applied")

	def buff_removed(self, evt):
		if isinstance(evt.buff, DamageAuraBuff):
			print(evt.buff.damage_dealt)
			self.spawn_pachyderm(evt.buff.damage_dealt)
		
	def spawn_pachyderm(self, dmg):
		self.aura += dmg
		while self.aura > self.threshold:
			self.aura -= self.threshold
			unit = CorruptElephant()
			apply_minion_bonuses(self, unit)
			self.owner.level.summon(owner=self.owner, unit=unit, target=self.owner)

	## "When 100 damage is dealt by any unit's aura, grant one random ally an aura dealing the same damage as their first spell, or arcane damage if that spell deals no
	## damage, for 15 turns." INCREDIBLY hard to implement with how damage sources work, abandon all hope ye who enter here. At best I can check if the source uses aura damage?
	#self.global_triggers[EventOnDamaged] = self.on_damage
	#def on_damage(self, evt):
	#	print(evt.source)
	#	if not isinstance(evt.source, DamageAuraBuff):
	#		return
	#	print("AURA FOUND")

class HindsightImmunity(Buff):
	def __init__(self, buff):
		Buff.__init__(self)
		self.buff = buff
		self.name = buff.name + " : Immunity"
		self.buff_type = BUFF_TYPE_BLESS
		self.stack_type = STACK_INTENSITY
		self.color = Tags.Enchantment.color
		self.description = "Immune to " + self.buff.name
		self.owner_triggers[EventOnBuffApply] = self.on_buff
		
	def on_buff(self, evt):
		if isinstance(evt.buff, type(self.buff)):
			if not evt.buff.applied:
				return
			self.owner.buffs.remove(evt.buff)
			evt.buff.unapply()

class Hindsight(Upgrade):
	def on_init(self):
		self.name = "Hindsight"
		self.level = 4
		self.tags = [Tags.Enchantment]
		self.asset = ["TcrsCustomModpack", "Icons", "hindsight"]

		self.description = "When any negative status effect wears off, become immune to it for 20 turns." ##This is very very long, should almost certainly be decreased.
		self.owner_triggers[EventOnBuffRemove] = self.on_buff
		self.duration = 20

	def on_buff(self, evt):
		if not evt.buff.buff_type == BUFF_TYPE_CURSE:
			return
		duration = self.get_stat('duration')
		self.owner.apply_buff(HindsightImmunity(evt.buff), duration)


class PleonasmFaker(Spell):
	def on_init(self):
		self.name = "Pleonasm"
		self.tags = []
		self.description = ""
		self.level = 1

class Pleonasm(Upgrade):
	def on_init(self):
		self.name = "Pleonasm"
		self.level = 0
		self.tags = [Tags.Sorcery]
		self.asset = ["TcrsCustomModpack", "Icons", "pleonasm"]
		self.description = "When you cast any spell, your on-cast effects trigger again. This does not recast the spell itself."
		self.owner_triggers[EventOnSpellCast] = self.on_cast
		
	def on_cast(self, evt):
		if type(evt.spell) == PleonasmFaker:
			return
		spell = PleonasmFaker()
		spell.name = "Pleonasm - " + str(evt.spell.name)
		spell.level = evt.spell.level
		spell.tags = evt.spell.tags
		self.owner.level.act_cast(self.owner, spell, evt.x, evt.y, pay_costs=False, queue=False)
		
class ChaosLord(Upgrade):
	def on_init(self):
		self.name = "Baron of Chaos"
		self.tags = [Tags.Chaos]
		self.level = 7 ##Needs some more buffs, level 7 is too weak.
		
		self.tag_bonuses[Tags.Chaos]['damage'] = 3
		self.tag_bonuses[Tags.Chaos]['duration'] = 3
		self.tag_bonuses[Tags.Chaos]['minion_duration'] = 3
		self.tag_bonuses[Tags.Chaos]['minion_damage'] = 3
		self.tag_bonuses[Tags.Chaos]['range'] = 3
		self.tag_bonuses[Tags.Chaos]['minion_range'] = 3

class Triskadecaphobia(Upgrade):
	def on_init(self):
		self.name = "Triskadecaphobia"
		self.tags = [Tags.Dark, Tags.Translocation]
		self.level = 5
		self.asset = ["TcrsCustomModpack", "Icons", "triskadekaphobia"]

		self.tiles = 0
		self.owner_triggers[EventOnUnitAdded] = self.enter
		self.lastx = 0
		self.lasty = 0

	def enter(self, evt):
		self.tiles = 0
		self.lastx = self.owner.x
		self.lasty = self.owner.y

	def distance(p1, p2, diag=False, euclidean=True): ##Suspiciously similar distance function
		if False:#diag
			return abs(p1.x - p2.x) + abs(p1.y - p2.y)
		if True:#euclidean:
			return math.sqrt(math.pow((p1.x - p2.x), 2) + math.pow((p1.y - p2.y), 2))
	
		return abs(p1.x - p2.x) + abs(p1.y - p2.y)

	def on_advance(self):
		dist = round( distance(Point(self.lastx, self.lasty), Point(self.owner.x, self.owner.y)) , 0)
		print(dist)
		self.tiles += dist
		self.lastx = self.owner.x
		self.lasty = self.owner.y
		self.tiles = round(self.tiles, 1)
		if math.floor(self.tiles) == 13:
			unit = DeathGhost() ##Make this a fearface?
			apply_minion_bonuses(self, unit)
			unit.turns_to_death = 6
			self.summon(unit)
			self.tiles = 0
		elif self.tiles > 13:
			units = list(self.owner.level.units)
			for unit in units:
				if unit == self.owner:
					continue
				unit.apply_buff(FearBuff(), 1)
			self.tiles = 0

	def get_description(self):
		return ("At the end of each turn, gain Phobia equal to the amount of tiles you've moved from your starting tile. "
				"Diagonal movement adds 1.4 times as many tiles. Always rounds down to the nearest whole number.\n"
				"If you have more than 13 Phobia, apply Fear to all enemies for 1 turn. If your Phobia is exactly 13 you summon a ghost. Both results reset Phobia to 0.\n"
				"Current Phobia: " + str(self.tiles))
	
	def get_extra_examine_tooltips(self):
		return [DeathGhost()]

def VoidWyrm():
	unit = Unit()
	unit.name = "Void Wyrm"
	unit.asset = ["TcrsCustomModpack", "Units", "wyrm_void"]
	unit.max_hp = 75

	unit.spells.append(VoidBreath())
	unit.spells.append(SimpleMeleeAttack(14, trample=True))

	unit.tags = [Tags.Arcane, Tags.Dragon, Tags.Living]
	unit.resists[Tags.Arcane] = 100
	
	unit.buffs.append(RegenBuff(8))
	unit.burrowing = True
	return unit

def GoldWyrm():
	unit = Unit()
	unit.name = "Gold Wyrm"
	unit.asset = ["TcrsCustomModpack", "Units", "wyrm_gold"]
	unit.max_hp = 75

	unit.spells.append(HolyBreath())
	unit.spells.append(SimpleMeleeAttack(14, trample=True))

	unit.tags = [Tags.Holy, Tags.Dragon, Tags.Living]
	unit.resists[Tags.Holy] = 100
	
	unit.buffs.append(RegenBuff(8))
	unit.burrowing = True
	return unit

class VoidCaller(Upgrade):
	def on_init(self):
		self.name = "Puredrake Voidcaller"
		self.tags = [Tags.Arcane, Tags.Holy, Tags.Dragon]
		self.level = 0 ##This is pretty strong at present. Doesn't seem too powerful with corruption effects like mordred's void tango.
		self.asset = ["TcrsCustomModpack", "Icons", "puredrake"]

		self.global_triggers[Level.EventOnMakeFloor] = self.on_floor
		self.global_triggers[EventOnDamaged] = self.on_damage
		self.wall_count = 0
		self.counter = 0
		
	def get_extra_examine_tooltips(self):
		return [VoidWyrm(), GoldWyrm()]

	def get_description(self):
		return ("For every 15 wall tiles turned into floor tiles, summon a Void Wyrm. For every 200 damage dealt by Arcane Minions, summon a Gold Wyrm.\n"
				"Walls Destroyed: %d\nDamage dealt: %d\n" % (self.wall_count, self.counter) )

	def on_floor(self, evt):
		if evt.was_wall:
			self.wall_count += 1
			
		if self.wall_count >= 15:
			unit = VoidWyrm()
			apply_minion_bonuses(self, unit)
			self.owner.level.summon(self.owner, unit, Point(evt.x, evt.y))
			self.wall_count -= 15

	def on_damage(self, evt):
		print(evt.source)
		print(evt.source.name)
		if not evt.source:
			return
		if not evt.source.owner:
			return
		if not hasattr(evt.source, 'tags'):
			return

		is_tagged_summon = False
		if evt.source.owner:
			if evt.source.owner.source:
				if hasattr(evt.source.owner.source, 'tags'):
					if Tags.Arcane in evt.source.owner.source.tags:
						is_tagged_summon = True

		if is_tagged_summon:
			self.counter += evt.damage
			while self.counter > 200:
				unit = GoldWyrm()
				apply_minion_bonuses(self, unit)
				self.summon(unit)
				self.counter -= 200

class TheFirstSeal(Upgrade):
	def on_init(self):
		self.name = "The First Seal"
		self.tags = [Tags.Holy, Tags.Dark, Tags.Orb]
		self.level = 0
		self.description = "When you deal 66 damage with [orb] spells or skills, and [holy] spells or skills, and [dark] spells or skills. Summon Conquest or buff your existing conquest."

class ArcticPoles(Upgrade):
	def on_init(self):
		self.name = "DEBUG"
		self.tags = [Tags.Ice]
		self.level = 0
		self.description = "DEBUG"
		##TODO something depending on how close you are to the top and bottom of the map?

class OnewithNothing(Upgrade):
	def on_init(self):
		self.name = "One With Nothing"
		self.tags = []
		self.description = "When you pass a turn, do something based on your spells with no charges."

class SwampQueen(Upgrade):
	def on_init(self):
		self.name = "Queen of the Swamp"
		self.tags = [Tags.Nature, Tags.Conjuration]
		self.description = "If there are 10 or more poisoned units on the map, summon the Swamp Queen. Only 1 may exist at a time."
		self.level = 0

class Convection(Upgrade):
	def on_init(self):
		self.name = "Thermal Convection"
		self.tags = [Tags.Fire, Tags.Ice]
		#self.asset = ["TcrsCustomModpack", "Icons", "cloudcover"]
		self.level = 0 
		self.description = "When you deal fire or ice damage to a unit, redeal that damage as the opposite element to all connected units besides the main target"

class DarkHolySacrificeThing(Upgrade):
	def on_init(self):
		self.name = "Placeholder name"
		self.tags = [Tags.Fire, Tags.Ice]
		#self.asset = ["TcrsCustomModpack", "Icons", "cloudcover"]
		self.level = 0 
		self.description = "Every 5 turns, if you have (or haven't) killed / summoned a holy minion, or a dark minion, or something similar, do something good (or bad)"

class Metamagic(Upgrade):
	def on_init(self):
		self.name = "Metamagic"
		self.level = 0
		self.description = "Every X turns gain metamagic, a buff which gives your highest level spell a bonus from your lowest level spell. It inherits: damage, minion damage, range, radius, num summons, breath damage, and duration. The spell can't gain more than 50% of its damage and it can gain only up to 2 of the other categories."

class Agoraphobia(Upgrade):
	def on_init(self):
		self.name = "Agoraphobia"
		self.level = 0
		self.description = "Your eye spells have a X% chance to fire when there are no enemies in line of sight / you have 6 walls surrounding you."

class StormSpirit(Upgrade):
	def on_init(self):
		self.name = "Storm Spirit"
		self.level = 0
		self.description = "Every 5 turns summon a storm spirit. Its max hp is equal to the lowest between the total damage dealt by ice spells, and the total damage dealt by lightning spells in the last 5 turns."

class Obelisk(Upgrade):
	def on_init(self):
		self.name = "Obelisk"
		self.level = 0
		self.description = "Gain a bonus on all of your spells and skills, lose this bonus if you cast the same spell twice per realm. Reset on each realm."

class Bluelaw(Upgrade):
	def on_init(self):
		self.name = "Blue Law"
		self.level = 0
		self.description = "Every 7th turn, stun all units on the map for 1 turn, including you."

class Preparation(Upgrade):
	def on_init(self):
		self.name = "Preparation"
		self.level = 0
		self.description = "When you enter a realm, cast all of your self targeted enchantment spells at yourself, and your conjuration spells targeting random squares."

class TheHitList(Upgrade):
	def on_init(self):
		self.name = "The Hit List"
		self.level = 0
		self.description = "When you enter a realm, 1 random enemy gains the target debuff. When it's killed, do something wicked sick."

class StatusDefenseField(Upgrade):
	def on_init(self):
		self.name = "Status Defense Field"
		self.level = 0
		self.description = "When you get frozen apply fire damage in an aoe. When you get stunned apply physical damage in an aoe. Etc."


class Gazette(Upgrade):
	def on_init(self):
		self.name = "The Wizard's Gazette"
		self.level = 0
		self.tags = [Tags.Enchantment]
		self.description = "Each turn summon a cantrip scroll."

class Torpor(Upgrade):
	def on_init(self):
		self.name = "Torpor Orb Effect"
		self.level = 0
		self.tags = [Tags.Enchantment]
		self.description = "Each attack or spell stuns the user for 1 second."

class Aposiopesis(Upgrade):
	def on_init(self):
		self.name = "Aposiopesis"
		self.level = 0
		self.tags = [Tags.Arcane]
		self.description = "When you stop channeling a spell, perform Y actions for each X turns spent channeling."

class TheRiddle(Upgrade):
	def on_init(self):
		self.name = "The Riddle"
		self.level = 0
		self.tags = [Tags.Arcane]
		self.description = "Each turn where you have done at least 3 of these summon a horseman. Cast a spell for free, cast a spell while payings its costs, moved, and passed a turn."
		self.owner_triggers[EventOnMoved] = self.on_move
		self.owner_triggers[EventOnSpellCast] = self.on_cast
		self.advanced = False
		self.passed = False
		self.cast_free = False
		self.cast_notfree = False


class LightningReflexes(Upgrade):
	def on_init(self):
		self.name = "Lightning Reflexes"
		self.level = 0
		self.tags = [Tags.Lightning]
		self.description = "You can cast 2 extra quick cast spells each turn."


# class Matryoshka(Upgrade):
# 	def on_init(self):
# 		self.name = "Cursed Matryoshka Doll"
# 		self.tags = [Tags.Metallic, Tags.Conjuration]
# 		self.level = 0
# 		self.description = "DEBUG"
# 		self.global_triggers[EventOnDeath] = self.on_death
	
# 	def on_death(self, evt):
# 		if not Tags.Metallic in evt.unit.tags and evt.unit.max_hp > 19:
# 			return
# 		golem = Golem()
# 		golem.max_hp = math.ceil(evt.unit.max_hp / 4) 
# 		self.summon(golem, Point(evt.unit.x,evt.unit.y))

# class RiftAlchemist(Upgrade):
# 	def on_init(self):
# 		self.name = "Rift Alchemist"
# 		self.tags = [Tags.Chaos]
# 		self.level = 0
# 		self.description = "Acquire alchemy reagents to brew into a potion at the end of each round"
# 		self.reagents = "Convert list into string eventually" ##TODO
# 		self.owner_triggers[]
# 		self.owner_triggers[EventOnUnitAdded] = self.on_enter_level

# 	def on_enter_level(self, evt):
# 		self.counter = self.counter_max


# 	def get_description(self):
# 		return ("After each level acquire alchemy reagents to make a potion.\n"
# 				"Reagent List: %d\n" % self.reagents)

def construct_skills():
	skillcon = [FromAshes, Lucky13, PsionicBlast, Crescendo, Librarian, BoneShaping, Chiroptyvern, Condensation, AngularGeometry, Discharge, PoisonousCopy, 
				IcyVeins, HolyMetalLantern, NightsightLantern, ContractFromBelow, MageArmor, Friction, Accelerator, ArclightEagle, Scrapheap, WeaverOfElements,
				WeaverOfOccultism, WeaverOfMaterialism, Mathemagics, QueenOfTorment, Cloudcover, WalkTheOrb, EyeSpellTrigger, Overheal, RimeorbLantern,
				ChaosScaleLantern, AuraReading, Hindsight, Pleonasm, Triskadecaphobia, VoidCaller, ChaosLord]
	for s in skillcon:
		Upgrades.skill_constructors.extend([s])