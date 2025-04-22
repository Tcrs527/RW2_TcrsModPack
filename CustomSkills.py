from msvcrt import kbhit
import sys

sys.path.append('../..')

import Spells
import Upgrades
from Game import *
from Level import *
from Monsters import *
from RareMonsters import BatDragon
from copy import copy
import math
import copy

from mods.TcrsCustomModpack.SharedClasses import *
from mods.TcrsCustomModpack.CustomSpells import MetalShard, Improvise, OpalescentEyeBuff, SeaSerpent, SeaWyrmBreath, SummonEyedra, ShrapnelBreath, SteelFangs, SummonBookwyrm, ScrollBreath

print("Custom Skills Loaded")

class Librarian(Upgrade):
	def on_init(self):
		self.name = "Librarian"
		self.tags = [Tags.Word, Tags.Sorcery]
		self.asset = ["TcrsCustomModpack", "Icons", "librarian"]
		self.level = 7
		self.description = ("Whenever you cast a level 5 or greater spell, summon a number of living scrolls equal to the spell's level." +
							"Word spells summon twice as many scrolls.\n" +
							"\nCan summon: [Fire], [Ice], [Lightning], [Nature], [Arcane], [Dark], [Holy], [Metallic], [Chaos], and [Blood] scrolls, depending on the tags of spell.")
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
		if evt.spell.level < 5:
			return
		maintags = copy.copy(evt.spell.tags)
		for exclude in self.excluded:
			if exclude in maintags:
				maintags.remove(exclude)
		mult = 1
		if Tags.Word in evt.spell.tags:
			mult = 2
		for i in range(evt.spell.level * mult):
			if len(maintags) > 1:
				random.shuffle(maintags)
			randtag = maintags[0]
			#print(randtag.name)
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
		self.asset = ["TcrsCustomModpack", "Icons", "from_the_ashes"]
		
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

	def get_description(self):
		return ("For every [fire] or [holy] unit that dies gain an ash charge. When you have at least 8 summon a phoenix.\n"
				"The phoenix has a ranged attack dealing [{minion_damage}_fire:fire] and your heavenly blast on a 2 turn cooldown. "
				"The phoenix has [{minion_health}_HP:minion_health], and explodes and reincarnates upon death.\n"
				"You can summon up to [{num_summons}:num_summons] Phoenix. "
				"If you have 8 ash charges upon entering a realm, immediately summon a phoenix.\n"
				"Ash Charges: %d" % self.fromashes).format(**self.fmt_dict())

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
		phoenicians = len([u for u in self.owner.level.units if not are_hostile(self.owner, u) and "Phoenix" in u.name and Tags.Fire in u.tags]) ##Conflicts with burning void and burning ice phoenixes
		if self.fromashes >= self.threshold and phoenicians < self.get_stat('num_summons'):
			self.fromashes -= self.threshold
			phoenix = Phoenix()
			apply_minion_bonuses(self, phoenix)
			self.summon(phoenix)
			grant_minion_spell(Spells.HolyBlast, phoenix, self.owner, cool_down=2)


class Lucky13Buff(Buff):
	def __init__(self, spell): 
		Buff.__init__(self)
		self.spell = spell
	
	def on_init(self):
		self.name = "Symbol of Chaos"
		self.color = Tags.Chaos.color
		self.buff_type = BUFF_TYPE_BLESS
		self.tag_bonuses[Tags.Chaos]['quick_cast'] = 1
		self.tag_bonuses[Tags.Chaos]['duration'] = 8
		self.tag_bonuses[Tags.Chaos]['minion_duration'] = 8
		
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
		return ("If exactly 8 levels of [chaos] spells are cast, gain the Symbol of Chaos.\n"
				"This buff grants: 8 duration, 8 minion duration, and quickcast to your next [chaos] spell.\n"
				"[Chaos] Spell Levels Cast: %d\n" % self.lucky13)

class Crescendo_dmg(Buff):	
	def on_init(self):
		self.name = "Crescendo!"
		self.color = Tags.Sorcery.color
		self.buff_type = BUFF_TYPE_BLESS
		self.stack_type = STACK_INTENSITY
		self.tag_bonuses[Tags.Sorcery]['damage'] = 5

class Crescendo(Upgrade):
	def on_init(self):
		self.name = "Crescendo"
		self.asset = ["TcrsCustomModpack", "Icons", "crescendo3"] ##TODO Fix corners
		self.tags = [Tags.Sorcery]
		self.level = 5

		self.duration = 20
		self.base = 1
		self.owner_triggers[EventOnSpellCast] = self.on_spell_cast

	def get_description(self):
		return ("Each time you cast a sorcery, if it's a higher level than the previous sorcery, your sorceries gain 5 stacking damage.\n"
				"Lasts 20 turns or until you cast any sorcery lower than the previous level."
				"Current Level: %d\n" % self.base)

	def on_spell_cast(self, evt):
		if Tags.Sorcery not in evt.spell.tags:
			return
		
		if self.base < evt.spell.level:
			self.base = evt.spell.level
			self.owner.apply_buff(Crescendo_dmg(), self.get_stat('duration'))
		elif self.base == evt.spell.level:
			pass
		else:
			self.base = evt.spell.level
			self.owner.remove_buffs(Crescendo_dmg)
			
	

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
		#self.breath_damage = ChiroDragon().spells[0].damage
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
			apply_minion_bonuses(self, drag)
			#drag.max_hp = self.get_stat('minion_health')
			#drag.spells[0].damage = self.get_stat('breath_damage')
			#drag.spells[0].range = self.get_stat('minion_range')
			#drag.spells[1].damage = self.get_stat('minion_damage')
			self.summon(drag)
			self.dark_spell_evt = 0
		


class Condensation(Upgrade):
	def on_init(self):
		self.name = "Condensation"
		self.tags = [Tags.Ice, Tags.Lightning, Tags.Nature, Tags.Slime]
		self.asset = ["TcrsCustomModpack", "Icons", "condensation"]
		self.level = 8
		
		self.radius = 1
		self.minion_health = 10
		self.minion_damage = 3
		self.minion_range = 3
		
	def get_description(self):
		return ("Each turn, convert blizzard clouds, thunder storms, and rain clouds within [{radius}_tile:radius] tile(s) into ice slimes, electric slimes, and water elementals respectively.").format(**self.fmt_dict())		

	def get_extra_examine_tooltips(self):
		return [IceSlime(), ElectricSlime(), WaterElemental()]

	def on_advance(self):
		for p in self.owner.level.get_points_in_rect(self.owner.x - self.radius, self.owner.y - self.radius, self.owner.x + self.radius, self.owner.y + self.radius):
			tile = self.owner.level.tiles[p.x][p.y]
			if isinstance(tile.cloud, BlizzardCloud):
				tile.cloud.kill()
				unit = IceSlime()
				apply_minion_bonuses(self, unit)
				self.summon(unit=unit, target=tile)
			if isinstance(tile.cloud, StormCloud):
				tile.cloud.kill()
				unit = ElectricSlime()
				apply_minion_bonuses(self, unit)
				self.summon(unit=unit, target=tile)
			elif isinstance(tile.cloud, RainCloud):
				tile.cloud.kill()
				unit = WaterElemental()
				apply_minion_bonuses(self, unit)
				self.summon(unit=unit, target=tile)
				unit.apply_buff(SoakedBuff(), 15)



class AngularGeometry(Upgrade): ##TODO This is not fit for launch.
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
		self.num_targets = 2
		self.charges = 0
		self.activated = False
	
	def on_enter_level(self, evt):
		#print(evt.unit.name)
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
		return ("Once a turn when you cast a [lightning] spell, gain sparks equal to the difference between the max and current charges of the spell.\n" +
				"Each turn deal [lightning] damage to [{num_targets}_enemies:num_targets] equal to your total number of sparks, "
				"then lose 10% of your sparks rounded up.\n" +
				"Current sparks: %d\n" % self.charges).format(**self.fmt_dict())
			
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
		self.description = ("Gain a stack of friction whenever you move. Gain two stacks for teleporting. Lose all stacks when you cast a [Fire] spell.\n"
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
		return ("Whenever you cast a [fire] spell targeting a [poisoned] unit, make a copy of that spell targeting one random enemy.\n"
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
			return
		
		#print(self.copies)
		copy_targets = [u for u in self.owner.level.units if are_hostile(self.owner, u) and u != unit]
		target = random.choice(copy_targets)
		self.copies += 1

		unit.remove_buff(Poison)
		if evt.spell.can_copy(target.x, target.y):
			self.owner.level.act_cast(self.owner, evt.spell, target.x, target.y, pay_costs=False)

	def on_advance(self):
		self.copies = 0


class IcyVeins(Upgrade):
	def on_init(self):
		self.name = "Icy Veins"
		self.tags = [Tags.Ice, Tags.Blood]
		self.level = 8 #Extremely ridiculously powerful effect, test at level 7 for sure. Super cool imho, Rebalance somehow. Perhaps only allied units? Then reduce threshold?
		self.asset = ["TcrsCustomModpack", "Icons", "icy_veins"]
		self.global_triggers[EventOnDamaged] = self.on_damaged
		self.iceblood = 0
		#if isinstance(s, Spell)
		
	def on_damaged(self, evt):
		#print("Source Name:")
		#print(evt.source.name)
		#print("Source Owner")
		#print(evt.source.owner.name)
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
		self.count = self.skill.get_stat('shot_cooldown')

	def make_knight(self):
		self.knight = EyeKnight()
		apply_minion_bonuses(self.skill, self.knight)
		self.summon(self.knight)

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
			self.count -= 1
			if self.count <= 0:
				self.count = self.skill.get_stat('shot_cooldown')
				self.knight.max_hp += self.skill.get_stat('minion_health') // 4
				self.knight.cur_hp += self.skill.get_stat('minion_health') // 4
				melee = [s for s in self.knight.spells if s.name == "Melee Attack"][0]
				melee.damage += self.skill.get_stat('minion_damage') // 4

class NightsightLantern(Upgrade):
	def on_init(self):
		self.name = "Nightsight Lantern"
		self.tags = [Tags.Dark, Tags.Eye, Tags.Conjuration]
		self.asset = ["TcrsCustomModpack", "Icons", "nightsight_lantern"]
		self.level = 5

		self.minion_health = 60
		self.minion_damage = 16
		self.shot_cooldown = 3

		self.owner_triggers[EventOnSpellCast] = self.on_spell_cast
		self.global_triggers[EventOnDeath] = self.on_death

	def get_description(self):
		return ("Whenever you cast a [dark] or [eye] spell, gain Nightsight with duration equal to the spell's level. Eye spells give 4 times their level. \n"
				"While you have Nightsight summon an eyeknight.\nEyeknights have [{minion_health}_max_hp:minion_health] and a [{minion_damage}_dark:dark] damage melee attack.\n"
				"When you cast an Eye enchantment, the eyeknight also casts it.\n"
			    "Each [3:duration] turns, decreasing with shot cooldown, the eyeknight gains 25% its base max hp and melee damage.\n").format(**self.fmt_dict())
	
	def get_extra_examine_tooltips(self):
		return [EyeKnight()]

	def on_death(self, evt):
		buff = self.owner.get_buff(NightsightBuff)
		if buff != None:
			if evt.unit == buff.knight:
				buff.make_knight

	def on_spell_cast(self, evt):
		if Tags.Dark in evt.spell.tags or Tags.Eye in evt.spell.tags:
			if Tags.Eye in evt.spell.tags:
				self.owner.apply_buff(NightsightBuff(self), evt.spell.level * 4)
				buff = self.owner.get_buff(NightsightBuff)
				if buff.knight != None and Tags.Enchantment in evt.spell.tags:
					spell = type(evt.spell)()
					spell.owner = buff.knight
					spell.caster = buff.knight
					self.owner.level.act_cast(buff.knight, spell, buff.knight.x, buff.knight.y, pay_costs=False, queue=True)
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
		
		self.tag_bonuses[Tags.Dark]['quick_cast'] = 1
		self.tag_bonuses[Tags.Chaos]['quick_cast'] = 1
		self.resists[Tags.Holy] = -100
		self.resists[Tags.Dark] = 100

		self.dtypes = [Tags.Dark, Tags.Chaos]
		self.owner_triggers[EventOnSpellCast] = self.on_cast

	def on_cast(self,evt):
		if Tags.Dark in evt.spell.tags or Tags.Chaos in evt.spell.tags:
			self.owner.deal_damage(5, Tags.Holy, self)

class ContractFromBelow(Upgrade):
	def on_init(self):
		self.name = "Contract from Below"
		self.tags = [Tags.Dark, Tags.Chaos]
		self.asset = ["TcrsCustomModpack", "Icons", "contract_from_below"]
		self.description =	("In each realm, after you summon 5 uniquely named demons, gain Demonic Contract.\n" + 
							"Demonic contract give: your [dark] and [chaos] spells quickcast, you -100 [holy] resist and 100% [dark] resist," +
							"and deals 5 [holy] damage to you per [dark] or [chaos] spell cast.")
		self.level = 6
		self.demons = {}
		self.global_triggers[EventOnUnitAdded] = self.on_unit_added
	

	def on_unit_added(self, evt):
		if evt.unit == self.owner:
			self.demons = {}
		else:
			#print(evt.unit.name)
			if not self.owner.level.are_hostile(self.owner, evt.unit) and Tags.Demon in evt.unit.tags:
				self.demons[evt.unit.name] = True
				if len(self.demons.keys()) >= 5:
					#print(self.demons.keys())
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
		self.description = ("Upon entering a realm, gain 25% resistance to damage types corresponding to each tag in each of your spells. Lasts [{duration}_turns:duration].\n" +
							"[Fire] spells grant [Fire] resistance, then repeat for all tags with damage types.\n" +
							"[Nature] tags grant [Poison] resistance, [Metallic] tags [Physical], [Blood] tags [Dark], and [Eye] tags [Arcane].").format(**self.fmt_dict())

	def on_unit_added(self, evt):
		if evt.unit == self.owner:
			restags = {Tags.Fire:0,Tags.Ice:0,Tags.Lightning:0,Tags.Arcane:0,Tags.Dark:0,Tags.Holy:0,Tags.Poison:0,Tags.Physical:0}
			spells = self.owner.spells
			for spell in spells:
				for t in spell.tags:
					if t == Tags.Nature:t = Tags.Poison
					elif t == Tags.Metallic:t = Tags.Physical
					elif t == Tags.Blood:t = Tags.Dark
					elif t == Tags.Eye:t = Tags.Arcane
					
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
		self.duration = 5

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
		self.level = 4
		
		self.owner_triggers[EventOnSpellCast] = self.on_cast
		self.damage = 5
		self.points = []
		self.spell_tags = []
		self.description = ("For every 3 [Fire], [Ice], or [Lightning] spells you cast, deal [{damage}_damage:damage] in a line between the target tile and the other spell's target tiles.\n" +
							"Deal [fire] damage if any of the spells had the [fire] tag, then repeat for [Ice] and [Lightning].\n"
							"Does not hurt you.\nDoes not work with free spells.").format(**self.fmt_dict())	

	def on_cast(self, evt):
		if not evt.pay_costs:
			return
		if Tags.Fire in evt.spell.tags or Tags.Ice in evt.spell.tags or Tags.Lightning in evt.spell.tags:
			p = Point(evt.x, evt.y)
			self.points.append(p)
			for tag in evt.spell.tags:
				if tag not in self.spell_tags and tag in self.tags:
					self.spell_tags.append(tag)
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
		self.ghostdict = {Tags.Arcane:GhostVoid, Tags.Dark:DeathGhost, Tags.Holy:HolyGhost, Tags.Blood:Bloodghast}
		
		self.minion_health = 4
		self.minion_damage = 2
		self.minion_duration = 5
	
	def get_description(self):
		return ("For every 3 [arcane], [dark], [holy], or [blood] spells you cast, summon ghosts at the target tile of each spell. Ghosts last [{minion_duration}_turns:minion_duration] turns.\n"
				"Summon 1 ghost for each of the specified tags, at each of the targeted tiles.\n"
				"Does not work with free spells.").format(**self.fmt_dict())

	def on_cast(self, evt):
		if not evt.pay_costs:
			return
		if not (Tags.Arcane in evt.spell.tags or Tags.Dark in evt.spell.tags or Tags.Holy in evt.spell.tags or Tags.Blood in evt.spell.tags):
			return
		for tag in evt.spell.tags:
			if tag not in self.spell_tags and tag in self.tags:
				self.spell_tags.append(tag)
		
		p = Point(evt.x, evt.y)
		self.points.append(p)
		
		if len(self.points) >= 3:
			print(self.spell_tags)
			if self.spell_tags == []:
				return
			for p in self.points:
				for tag in self.spell_tags:
					unit = self.ghostdict[tag]()
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
	unit.spells.append(SimpleMeleeAttack(5))
	unit.tags = [Tags.Slime]
	unit.resists[Tags.Poison] = 100
	return unit

class WeaverOfMaterialism(Upgrade):
	def on_init(self):
		self.name = "Weave the Material"
		self.tags = [Tags.Nature, Tags.Dragon, Tags.Metallic, Tags.Slime]
		self.asset = ["TcrsCustomModpack", "Icons", "weaver_of_material"]
		self.description = ("For every 3 [nature], [dragon], and [metallic] spells you cast, summon a slime at the third spell's target tile.\n" +
							"If the [nature] tag was in any spell, the slime gains max hp and spawns additional green slimes.\n"
							"If the [dragon] tag was in any spell, it gains a breath attack.\n"
							"If the [metallic] tag was in any spell, it gains metallic resistances and melee retaliation damage.\n" ##TODO implement slime
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
		if not (Tags.Nature or Tags.Dragon or Tags.Metallic in evt.spell.tags):
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
			self.owner.level.summon(self.owner, unit, self.points[-1])
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
			unit.buffs.append(SlimeBuff(spawner=GreenSlime))
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
		self.description = "Each 10 turns summon a scrap golem. For each construct or metallic unit that died during those 10 turns, it gains either 7 health, or 3 damage."
		self.level = 4 ##Directly comparable to boneguard.
		self.global_triggers[EventOnDeath] = self.on_death
		self.scrap = 0
		self.counter = 0
		self.minion_health = 21
		self.minion_damage = 9
		
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

class ArclightEagle(Upgrade):
	def on_init(self):
		self.name = "Arclight Eagle" ##Obviously inspired by Arclight Phoenix
		self.tags = [Tags.Lightning, Tags.Conjuration]
		self.asset = ["TcrsCustomModpack", "Icons", "arclight_eagle"]
		self.description = "On any turn you cast at least 2 spells, one of which is [lightning], summon an eagle. The eagle inherits upgrades from your Flock of Eagles spell."
		self.level = 5
		self.owner_triggers[EventOnSpellCast] = self.on_cast
		self.spells_cast = 0
		self.lightning = False


	def on_cast(self, evt):
		if Tags.Lightning in evt.spell.tags:
			self.lightning = True
		self.spells_cast += 1

	def on_advance(self):
		if self.spells_cast >= 2 and self.lightning == True:
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
		self.level = 8
		
		self.damage = 13

	def on_advance(self):
		if not self.owner.has_buff(Arithmetic):
			#print(self)
			#difficulty = self.owner.level.gen_params.difficulty
			self.owner.apply_buff(Arithmetic(self))

	def get_description(self):
		return ("Each turn gain the Arithmagics buff if you don't have it. The buff has an integer value between 1 and {damage}, " +
				"which when reduced to exactly 0, deals [{damage}:poison] poison damage to all units except the Wizard, then permanently gains 1 damage.\n" + 
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
				" Repeat for [Poison] damage with the Frozen debuff, and [Arcane] damage with Poisoned and Acidified debuffs.\n"
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
		self.stack_type	= STACK_REPLACE
		self.color = Tags.Enchantment.color
		self.description = "Resistant to the cloud damage type."
		self.resists = {}

class Cloudcover(Upgrade):
	def on_init(self):
		self.name = "Cloud Cover"
		self.tags = [Tags.Enchantment]
		self.asset = ["TcrsCustomModpack", "Icons", "cloudcover"]
		self.level = 5 ##Tentative level 5-6 this is incredibly good with stormcaller, this is very okay with everything else though.
		self.duration = 1
		self.cloud_dict = {BlizzardCloud:Tags.Ice, StormCloud:Tags.Lightning, PoisonCloud:Tags.Poison, FireCloud:Tags.Fire, Sandstorm:Tags.Physical} #Add  bloodclouds, consider rain cloud?

	def get_description(self):
		return ("When you end your turn in a cloud, gain 75 resistance to that cloud's damage type for [{duration}_turns:duration] turn(s).\n" +
				"Applies to: Blizzards, Thunderstorms, Poison Clouds, and Sandstorms.").format(**self.fmt_dict())

	def on_advance(self):
		cloud = self.owner.level.tiles[self.owner.x][self.owner.y].cloud
		if cloud:
			c_type = type(cloud)
			if c_type not in self.cloud_dict.keys():
				return
			tag = self.cloud_dict[c_type]
			if c_type in self.cloud_dict:
				duration = self.get_stat('duration')
				self.owner.apply_buff(CloudcoverBuff(tag), duration)


class EyeSpellTrigger(Upgrade):
	def on_init(self):
		self.name = "Eye of Providence"
		self.level = 5
		self.tags = [Tags.Holy, Tags.Eye]
		self.asset = ["TcrsCustomModpack", "Icons", "eye_of_providence"]
		self.description = "When you cast a holy spell, advance your eye spell buff cooldowns by one turn. Activate them if they reach 0."
		self.owner_triggers[EventOnSpellCast] = self.on_cast
		
	def on_cast(self, evt):
		if Tags.Holy not in evt.spell.tags:
			return
		eyebuffs = []
		for b in self.owner.buffs:
			if isinstance(b, Spells.ElementalEyeBuff):
				eyebuffs.append(b)
		if eyebuffs == []:
			return
		for b in eyebuffs:
			b.on_advance()


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
		self.tags = [Tags.Holy, Tags.Nature, Tags.Conjuration]
		self.asset = ["TcrsCustomModpack", "Icons", "overheal"]
		self.global_triggers[EventOnHealed] = self.on_heal
		self.total = 0
		self.minion_health = 28
		self.minion_damage = 7

	def get_description(self):
		return ("Whenever a unit heals, gain Vitality stacks equal to the amount of missing life healed.\n"
				"Each turn consume up to 75 vitality to summon a false prophet or an armored satyr."
				"Current Vitality: %d\n" % self.total)

	def get_extra_examine_tooltips(self):
		return [FalseProphet(), SatyrArmored()]

	def on_heal(self, evt):
		#for s in self.owner.spells:
		#	print(s)
		if not evt.source:
			return
		if not hasattr(evt.source, 'tags'):
			return
		heal = evt.heal
		self.total -= heal

	def on_advance(self):
		if self.total < 75:
			return
		unit = random.choice([FalseProphet(), SatyrArmored()])
		self.total -= 75
		apply_minion_bonuses(self, unit)
		self.summon(unit)

class WalkTheOrb(Upgrade):
	def on_init(self):
		self.name = "Sphere Sorcery"
		self.level = 5
		self.tags = [Tags.Sorcery, Tags.Orb]
		self.asset = ["TcrsCustomModpack", "Icons", "orbwalker"]
		
		self.owner_triggers[EventOnSpellCast] = self.on_cast
		self.tagconv = TagToDmgTagConvertor()
		
		self.damage = 20
		
	def get_description(self):
		return ("When you cast an orb spell deal 20 damage to one random enemy for each different tag in orb spells you know. "
				"Deal 5 times as much damage if you used an orb to orb walk.\n"
				" Converts all damage tags e.g. [Arcane] to [Arcane] damage, and also converts [Metallic] to [Physical], and [Blood] to [Dark].").format(**self.fmt_dict())

	def on_cast(self, evt):
		if Tags.Orb not in evt.spell.tags:
			return
		multiplier = 1
		if ( evt.spell.get_stat('orb_walk') and evt.spell.get_orb(evt.x, evt.y) ):
			multiplier = 5

		orb_tags = []
		for s in self.owner.spells:
			if Tags.Orb not in s.tags:
				continue
			for tag in s.tags:
				if tag not in orb_tags:
					orb_tags.append(tag)
		for tag in orb_tags:
			if tag in self.tagconv:
				dmg_tag = self.tagconv[tag]
				targets = [u for u in self.owner.level.units if self.owner.level.are_hostile(self.owner, u)]
				if targets != []:
					targ = random.choice(targets)
					self.owner.level.deal_damage(targ.x, targ.y, self.damage * multiplier, dmg_tag, self)
					


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
		self.name = "Rimeorb Lantern"
		
	def on_advance(self):
		if not self.owner.has_buff(RimeorbDamageBuff):
			buff = RimeorbDamageBuff(self.skill)
			buff.source = self
			self.owner.apply_buff(buff)
		orbs = [t for t in self.owner.level.units if not self.owner.level.are_hostile(t, self.owner) and not t.has_buff(RimeorbDamageBuff) and (" Orb" in t.name or Tags.Ice in t.tags)]
		if orbs == []:
			return
		o = random.choice(orbs)
		buff = RimeorbDamageBuff(self.skill)
		buff.source = self
		o.apply_buff(buff)

	def on_unapplied(self):
		#print("Unapply")
		self.owner.remove_buffs(RimeorbDamageBuff)
		orbs = [t for t in self.owner.level.units if t.has_buff(RimeorbDamageBuff)]
		if orbs == []:
			return
		#print(orbs)
		for o in orbs:
			o.remove_buffs(RimeorbDamageBuff)

class RimeorbLantern(Upgrade):
	def on_init(self):
		self.name = "Rimeorb Lantern"
		self.tags = [Tags.Ice, Tags.Orb, Tags.Enchantment]
		self.asset = ["TcrsCustomModpack", "Icons", "rimeorb_lantern"]
		self.level = 5 ##Aiming for level 4 or 5. Scales extremely poorly at present. Wouldn't mind a source of aura damage somewhere. Applies to ice minions now, will work well with icy thorns, ice wall, etc. Strong with some setup.
		self.radius = 6
		self.aura_damage = 2
		self.owner_triggers[EventOnSpellCast] = self.on_spell_cast

	def get_description(self):
		return ("Whenever you cast an [Ice] or [Orb] spell, gain Rimeorb Aura with duration equal to the spell's level. Orb spells give 3 times their level. \n"
				"Rimeorb Aura grants you a [{radius}_tile:radius] ice damage aura dealing 2 damage to enemies each turn. Each turn you also grant one orb or [ice] minion the same aura. "
				"Units retain the aura until the buff ends.").format(**self.fmt_dict())

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
		self.damage = 20
		self.level = 1
		self.tags = [Tags.Dragon, Tags.Chaos]
		self.range = 4

	def per_square_effect(self, x, y):
		damage_type = random.choice([Tags.Fire, Tags.Lightning, Tags.Physical])
		self.caster.level.deal_damage(x, y, self.damage, damage_type, self)

class ChaosScaleBuff(Buff):
	def __init__(self, skill):
		self.skill = skill
		self.minion_damage = skill.get_stat('minion_damage') #TODO check breath damage
		self.range = self.skill.get_stat('range')
		self.cooldown = 2
		Buff.__init__(self)
		
	def on_init(self):
		self.name = "Riotscale Rage"
		self.tags = [Tags.Dragon, Tags.Chaos]
		self.color = Tags.Dragon.color
		self.stack_type = STACK_DURATION
		self.buff_type = BUFF_TYPE_BLESS

	def on_advance(self):
		self.cooldown -= 1
		self.range += 1
		if self.cooldown > 0:
			return
		targets = [t for t in self.owner.level.get_units_in_ball(self.owner, self.range) if are_hostile(self.owner, t) and self.owner.level.can_see(t.x, t.y, self.owner.x, self.owner.y)]
		if targets == []:
			return
		breath = self.owner.get_or_make_spell(RiotscaleBreath)
		breath.range = self.range
		breath.source = self
		breath.damage = self.minion_damage
		unit = random.choice(targets)
		self.owner.level.act_cast(self.owner, breath, unit.x, unit.y, pay_costs=False)
		self.range = self.skill.get_stat('range')
		self.cooldown = 2
		
class ChaosScaleLantern(Upgrade):
	def on_init(self):
		self.name = "Riotscale Lantern"
		self.tags = [Tags.Dragon, Tags.Chaos]
		self.asset = ["TcrsCustomModpack", "Icons", "riotscale_lantern"]
		self.level = 4
		self.owner_triggers[EventOnSpellCast] = self.on_spell_cast
		
		self.minion_damage = 20
		self.range = 4

	def get_description(self):
		return ("Whenever you cast a [Dragon] or [Chaos] spell, gain Riotscale Rage with duration equal to the spell's level. Dragon spells give 3 times their level.\n"
				"The buff gives you an automatic level 1 [dragon] [chaos] breath attack with a 1 turn cooldown.\n"
				" The breath attack has a default range of [{range}_tile:range] and deals [{minion_damage}_:dragon] [Physical], [Fire], or [Lightning] damage randomly."
				" Each turn the breath gains 1 range, but when it activates its range resets.").format(**self.fmt_dict())

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
		self.asset = ["TcrsCustomModpack", "Icons", "aura_reading"]
		
		self.global_triggers[EventOnUnitAdded] = self.on_enter
		self.global_triggers[EventOnBuffApply] = self.buff_applied
		self.global_triggers[EventOnBuffRemove] = self.buff_removed
		self.global_triggers[EventOnDeath] = self.on_death
		
		self.global_bonuses['aura_damage'] = 2

		self.aura_damage = 2
		self.minion_health = 55
		self.minion_damage = 12
		self.duration = 20

	def get_description(self):
		return ("When an ally enters with, or is given, a damaging aura, that unit also gains a 2 damage physical aura with the same size for [{duration}_turns:duration] turns.\n" +
				"When a unit's aura ends, summon an elephant which lasts for 1 turn for each 10 damage the aura did.\n").format(**self.fmt_dict())

	def get_extra_examine_tooltips(self):
		return [CorruptElephant()]

	def copy_aura(self, aura):
		buff = DamageAuraBuff(damage=aura.damage, radius=aura.radius, damage_type=[Tags.Physical], friendly_fire=False)
		buff.stack_type = STACK_REPLACE
		buff.color = Tags.Physical.color
		buff.name = "Physical Aura"
		buff.source = self
		return buff

	def on_enter(self, evt):
		if are_hostile(self.owner, evt.unit):
			return
		aura = evt.unit.get_buff(DamageAuraBuff)
		if aura == None:
			return
		if aura.name == "Physical Aura":
			return
		buff = self.copy_aura(aura)
		evt.unit.apply_buff(buff, self.get_stat('duration'))

	def buff_applied(self, evt):
		if are_hostile(self.owner, evt.unit):
			return
		if not isinstance(evt.buff, DamageAuraBuff) or evt.buff.name == "Physical Aura":
			return
		buff = self.copy_aura(evt.buff)
		evt.unit.apply_buff(buff, self.get_stat('duration'))

	def spawn_pachyderm(self, duration):
		if duration <= 0:
			return
		unit = CorruptElephant()
		unit.turns_to_death = duration
		apply_minion_bonuses(self, unit)
		self.owner.level.summon(owner=self.owner, unit=unit, target=self.owner)

	def on_death(self, evt):
		buff = evt.unit.get_buff(DamageAuraBuff)
		if buff == None:
			return
		duration = buff.damage_dealt // 10
		self.spawn_pachyderm(duration)

	def buff_removed(self, evt):
		if isinstance(evt.buff, DamageAuraBuff):
			duration = evt.buff.damage_dealt // 10
			self.spawn_pachyderm(duration)

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

		self.owner_triggers[EventOnBuffRemove] = self.on_buff
		self.duration = 5

	def get_description(self):
		return ("When any negative status effect wears off, become immune to it for [{duration}_turns:duration].").format(**self.fmt_dict())

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
		self.level = 5
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
		self.asset = ["TcrsCustomModpack", "Icons", "baron_of_chaos"]
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

		self.minion_health = 1
		self.minion_damage = 2

		self.tiles = 0
		self.owner_triggers[EventOnUnitAdded] = self.enter
		self.lastx = 0
		self.lasty = 0

	def get_description(self):
		return ("At the end of each turn, gain Phobia equal to the amount of tiles you've moved from your starting tile. "
				"Diagonal movement adds 1.4 times as many tiles. Always rounds down to the nearest whole number.\n"
				"If you have more than 13 Phobia, apply Fear to all enemies for 1 turn. If your Phobia is exactly 13 you summon a Fearface. Both results reset Phobia to 0.\n"
				"Current Phobia: " + str(self.tiles))
	
	def get_extra_examine_tooltips(self):
		return [Fearface()]

	def enter(self, evt):
		self.tiles = 0
		self.lastx = self.owner.x
		self.lasty = self.owner.y

	def distance(p1, p2, diag=False, euclidean=True): ##Suspiciously similar distance function
		return math.sqrt(math.pow((p1.x - p2.x), 2) + math.pow((p1.y - p2.y), 2))

	def on_advance(self):
		dist = round( distance(Point(self.lastx, self.lasty), Point(self.owner.x, self.owner.y)) , 0)
		self.tiles += dist
		self.lastx = self.owner.x
		self.lasty = self.owner.y
		self.tiles = round(self.tiles, 1)
		if math.floor(self.tiles) == 13:
			unit = Fearface()
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
		self.level = 6 ##This is pretty strong at present. Doesn't seem too powerful with corruption effects like mordred's void tango.
		self.asset = ["TcrsCustomModpack", "Icons", "puredrake"]

		self.global_triggers[Level.EventOnMakeFloor] = self.on_floor
		self.global_triggers[EventOnDamaged] = self.on_damage
		self.wall_count = 0
		self.counter = 0
		
		self.minion_health = 75
		self.minion_damage = 14
		#self.breath_damage = 9 #Commented out in case breath damage returns
		
	def get_extra_examine_tooltips(self):
		return [VoidWyrm(), GoldWyrm()]

	def get_description(self):
		return ("For every 15 wall tiles turned into floor tiles, summon a Void Wyrm.\n"
				"For every 200 damage dealt by Arcane Minions, summon a Gold Wyrm.\n"
				"Walls Destroyed: %d\nDamage dealt: %d\n" % (self.wall_count, self.counter) )

	def make_wyrm(self, void):
		if void:
			unit = VoidWyrm()
		else:
			unit = GoldWyrm()

		apply_minion_bonuses(self, unit)
		#unit.max_hp = self.get_stat('minion_health')
		#unit.spells[0].damage = self.get_stat('breath_damage')
		#unit.spells[1].damage = self.get_stat('minion_damage')
		return unit

	def on_floor(self, evt):
		if evt.was_wall:
			self.wall_count += 1
			
		if self.wall_count >= 15:
			unit = self.make_wyrm(void=True)
			self.owner.level.summon(self.owner, unit, Point(evt.x, evt.y))
			self.wall_count -= 15

	def on_damage(self, evt): ##Somewhat modified form of scent of blood. Didn't fit my exact requirements so I had to fix it up.
		if not evt.source:
			return
		if not evt.source.owner:
			return
		if not hasattr(evt.source, 'tags'):
			return
		#print(evt.source)
		#print(evt.source.name)

		is_tagged_summon = False
		if evt.source.owner:
			if isinstance(evt.source.owner, Unit) and Tags.Arcane in evt.source.owner.tags:
				is_tagged_summon = True
			#	print(evt.source.owner.source.name)
			# if evt.source.owner.source:
			# 	if hasattr(evt.source.owner.source, 'tags'):
			# 		if Tags.Arcane in evt.source.owner.source.tags:
			# 			is_tagged_summon = True
			# 			print(evt.source.owner.source.name)

		if is_tagged_summon:
			self.counter += evt.damage
			while self.counter > 200:
				unit = self.make_wyrm(void=False)
				self.summon(unit)
				self.counter -= 200


class OrbWeaver(Upgrade): ##Shamelessly modified version of silkshifter.
	def on_init(self):
		self.name = "Orb Weaver"
		self.level = 6 ##As strong as burning aura, so pretty strong
		self.tags = [Tags.Nature, Tags.Metallic, Tags.Conjuration, Tags.Orb]
		self.asset = ["TcrsCustomModpack", "Icons", "orbweaver"] ##TODO make colours slightly better. Low Priority
		self.owner_triggers[EventOnSpellCast] = self.on_cast
		
		example = SpiderFurnace()
		self.minion_health = example.max_hp
		self.minion_damage = example.spells[0].damage
		
	def on_applied(self, owner):
		self.owner.tags.append(Tags.Spider)

	def on_unapplied(self):
		self.owner.tags.remove(Tags.Spider)

	def get_description(self):
		return ("You are a [spider].\n"
				"Passively spawn a web each turn on a random adjacent tile.  Webs will not spawn on top of units or walls.\n"
				"When you cast an [Orb] spell while inside a web, you summon a copper spider.\n"
				"When you target a web with an [Orb] spell, summon a furnace spider.")

	def get_extra_examine_tooltips(self):
		return [SpiderFurnace(), SpiderCopper()]

	def on_advance(self):
		if not any(are_hostile(self.owner, u) for u in self.owner.level.units):
			return
		spawn_webs(self.owner)
		
	def on_cast(self, evt):
		if Tags.Orb not in evt.spell.tags:
			return
		web = self.owner.level.tiles[self.owner.x][self.owner.y].cloud
		if web and (type(web) == SpiderWeb):
			unit = SpiderCopper()
			apply_minion_bonuses(self, unit)
			self.summon(unit)
		target = self.owner.level.tiles[evt.x][evt.y].cloud
		if target and (type(target) == SpiderWeb):
			unit_alt = SpiderFurnace()
			apply_minion_bonuses(self, unit_alt)
			self.summon(unit_alt)


class LightningReflexes(Upgrade):
	def on_init(self):
		self.name = "Unnatural Haste"
		self.level = 5
		self.tags = [Tags.Sorcery]
		self.asset = ["TcrsCustomModpack", "Icons", "unnaturalhaste"]
		self.owner_triggers[EventOnSpellCast] = self.on_cast
		
		self.counter = 0
		self.num_targets = 2

	def get_description(self):
		return ("You can cast [{num_targets}:num_targets] extra quick cast spells each turn.").format(**self.fmt_dict())

	def on_cast(self, evt):
		if evt.pay_costs == False:
			return
		self.counter += 1
		if self.counter < 2 + self.get_stat('num_targets'): ## 1st, 2nd, spell are the ones this adds, 3rd is your normal quick cast spell, and the 4th ends your turn.
			self.owner.quick_cast_used = False
			return
		self.owner.quick_cast_used = True
	
	def on_advance(self):
		self.counter = 0


class TheFirstSeal(Upgrade):
	def on_init(self):
		self.name = "The First Seal"
		self.tags = [Tags.Holy, Tags.Chaos, Tags.Conjuration]
		self.level = 5
		self.asset = ["TcrsCustomModpack", "Icons", "thefirstseal"]

		self.minion_health = 66
		self.minion_damage = 9

		self.owner_triggers[EventOnSpellCast] = self.on_cast
		self.global_triggers[EventOnUnitAdded] = self.on_unit_enter
		self.holy_spells = 0
		self.unit_count = 0
		
	def get_description(self):
		return ("For every 6 [Holy] spells you cast, summon a warlock for 16 turns.\n"
				"For every 66 [Chaos] or [Demon] units that are summoned, summon a white rider.").format(**self.fmt_dict())

	def get_extra_examine_tooltips(self):
		return [Warlock(), WhiteRider()]

	def on_cast(self, evt):
		if not Tags.Holy in evt.spell.tags:
			return
		self.holy_spells += 1
		if self.holy_spells >= 6:
			self.holy_spells -= 6
			unit = Warlock()
			apply_minion_bonuses(self, unit)
			minion_duration = self.get_stat('minion_duration',base=16)
			unit.turns_to_death = minion_duration
			self.owner.level.summon(self.owner, unit)


	def on_unit_enter(self, evt):
		if Tags.Chaos in evt.unit.tags or Tags.Demon in evt.unit.tags:
			self.unit_count += 1
		if self.unit_count >= 66:
			self.unit_count = 0
			unit = WhiteRider()
			unit.spells.pop(0)
			apply_minion_bonuses(self, unit)
			self.owner.level.summon(self.owner, unit)

def make_archon():

	angel = Unit()
	angel.name = "Archon"
	angel.tags = [Tags.Holy]

	angel.max_hp = 77
	angel.resists[Tags.Holy] = 100
	angel.resists[Tags.Dark] = 75
	angel.resists[Tags.Lightning] = 75

	lightning = ArchonLightning()
	lightning.damage = 14
	lightning.range = 7
	angel.spells.append(lightning)
	angel.flying = True
	return angel


def make_angel():
	angel = Unit()
	angel.name = "Seraph"
	angel.asset_name = "seraphim"
	angel.tags = [Tags.Holy]

	angel.max_hp = 33
	angel.shields = 3
	angel.resists[Tags.Holy] = 100
	angel.resists[Tags.Dark] = 75
	angel.resists[Tags.Fire] = 75

	sword = SeraphimSwordSwing()
	sword.damage = 14
	sword.arcane = False
	angel.spells.append(sword)
	angel.flying = True
	return angel

class DarkBargain(Upgrade):
	def on_init(self):
		self.name = "Dark Bargain"
		self.level = 7
		self.tags = [Tags.Dark]
		self.asset = ["TcrsCustomModpack", "Icons", "dark_bargain"]
		self.description = "After 10 turns summon hostile angels. The amount summoned is equal to 2, plus the realm number. This can activate after the realm is cleared."
		
		self.global_bonuses['max_charges'] = 1
		self.global_bonuses['num_targets'] = 1
		self.global_bonuses['range'] = 1
		
		self.owner_triggers[EventOnUnitAdded] = self.on_enter
		self.count = 0

	def get_extra_examine_tooltips(self):
		return [make_angel(), make_archon()]

	def on_enter(self, evt):
		self.count = 0

	def on_advance(self):
		self.count += 1
		if self.count == 10:
			difficulty = self.owner.level.gen_params.difficulty
			for i in range(2 + difficulty):
				unit = random.choice([make_angel(), make_archon()])
				self.summon(unit, radius=99, sort_dist=False)
				unit.team = 1


class TheHitDebuff(Buff):
	def __init__(self, skill):
		self.skill = skill
		Buff.__init__(self)
		self.name = "Targeted"
		self.stack_type = STACK_NONE
		self.buff_type = BUFF_TYPE_CURSE
		self.asset = ["TcrsCustomModpack", "Misc", "hitlist_buff"]
		self.color = Tags.Sorcery.color
		self.owner_triggers[EventOnDeath] = self.on_death

	def on_death(self, evt):
		self.skill.global_bonuses['damage'] += 1
		self.skill.owner.global_bonuses['damage'] += 1

class TheHitList(Upgrade):
	def on_init(self):
		self.name = "The Hit List"
		self.tags = [Tags.Sorcery, Tags.Enchantment]
		self.level = 4
		self.asset = ["TcrsCustomModpack", "Icons", "hitlist_icon"]

		self.owner_triggers[EventOnUnitAdded] = self.on_unit_added
		self.global_bonuses['damage'] = 1
		self.duration = 20
		##Inspired by the risk of rain 1 item, this makes you play very differently. I think it's cool, but it's very limiting in which builds can wipe the whole map in 15. Encourages spells like pillar of fire

	def get_description(self):
		return ("When you enter a realm, 1 random enemy gains the 'targeted' debuff."
				" If it dies within [{duration}_turns:duration], this skill gains 1 damage permanently.").format(**self.fmt_dict())

	def on_unit_added(self, evt):
		units = [u for u in self.owner.level.units if are_hostile(u, self.owner)]
		target = random.choice(units)
		target.apply_buff(TheHitDebuff(self), self.get_stat('duration'))


class ArcticPoleBuff(Buff):
	def __init__(self):
		Buff.__init__(self)
		self.name = "Polar Wizard"
		self.stack_type = STACK_INTENSITY
		self.buff_type = BUFF_TYPE_BLESS
		self.show_effect = False
		self.asset = ["TcrsCustomModpack", "Misc", "polarwizard_buff"]
		self.color = Tags.Ice.color
		self.tag_bonuses[Tags.Ice]['damage'] = 1

class ArcticPoles(Upgrade):
	def on_init(self):
		self.name = "Polar Wizard"
		self.tags = [Tags.Ice]
		self.level = 4
		self.asset = ["TcrsCustomModpack", "Icons", "polarwizard"]
		
		self.size_y = 31
		self.duration = 10

	def get_description(self):
		return ("Gain the Polar Wizard buff each turn you are within 5 tiles of the top of bottom of the realm."
				" Each stack grants [ice] spells and skills 1 damage. Lasts [{duration}_turns:duration].").format(**self.fmt_dict())

	def on_advance(self):
		self.size_y = self.owner.level.height
		y = self.owner.y
		if y < 5 or y > (self.size_y - 5):
			self.owner.apply_buff(ArcticPoleBuff(), self.get_stat('duration'))


class Overkill(Upgrade):
	def on_init(self):
		self.name = "Overkill"
		self.level = 4
		self.tags = [Tags.Sorcery]
		self.asset = ["TcrsCustomModpack", "Icons", "overkill"]
		
		self.global_triggers[EventOnDamaged] = self.on_damage
		self.radius = 5

	def get_description(self):
		return ("When a [sorcery] damage source deals more than 75% of a unit's maximum hp in one hit, "
				" deal that unit's max hp, as that same damage type, to one target within [{radius}_tile:radius] tiles.").format(**self.fmt_dict())

	def on_damage(self, evt):
		if not hasattr(evt.source, 'tags'):
			return
		if Tags.Sorcery in evt.source.tags:
			if not evt.damage > (evt.unit.max_hp) * 0.75:
				return
			targets = self.owner.level.get_units_in_ball(evt.unit, self.get_stat('radius'))
			targets = [t for t in targets if are_hostile(t, self.owner) and t != evt.unit]
			if len(targets) == 0:
				return
			random.shuffle(targets)
			targets[0].deal_damage((evt.damage), evt.damage_type, self)


def RecycloneUnit():
	unit = Unit()
	unit.name = "Recyclone"
	unit.asset = ["TcrsCustomModpack", "Units", "recyclone2"]
	unit.max_hp = 40

	unit.spells.append(LeapAttack(damage=8, range=4))

	unit.flying = True
	unit.tags = [Tags.Construct, Tags.Nature, Tags.Metallic]
	unit.resists[Tags.Poison] = 100
	unit.resists[Tags.Physical] = 50

	return unit

class Recyclone(Upgrade):
	def on_init(self):
		self.name = "Recyclone"
		self.tags = [Tags.Nature, Tags.Conjuration, Tags.Metallic]
		self.level = 5
		self.asset = ["TcrsCustomModpack", "Icons", "recyclone_icon"]

		self.minion_health = 40
		self.minion_damage = 8
		self.minion_range = 4
		self.count = 0

		self.owner_triggers[EventOnItemUsed] = self.on_item
		self.owner_triggers[EventOnUnitAdded] = self.on_enter

	def get_description(self):
		return ("Whenever you enter a new level or use an item, summon a Recyclone. It has [{minion_health}_HP:minion_health], and"
				" a [{minion_damage}_physical:physical] damage charge attack with [{minion_range}_tile:minion_range] range.\n"
				"This skill permanently gains 10 minion life, and 2 minion damage whenever you use a consumable item, and 1 minion range for every 3 items.").format(**self.fmt_dict())

	def on_item(self, evt):
		self.count += 1
		self.minion_health += 10
		self.minion_damage += 2
		if self.count % 3 == 0:
			self.minion_range += 1
		self.summon_cyclone()

	def summon_cyclone(self):
		cyclone = RecycloneUnit()
		cyclone.max_hp = self.get_stat('minion_health')
		cyclone.spells[0].damage = self.get_stat('minion_damage')
		cyclone.spells[0].range = self.get_stat('minion_range')
		self.summon(cyclone, sort_dist=False)

	def on_enter(self, evt):
		self.summon_cyclone()
		

class OrdersBuff(Buff):
	def __init__(self, skill, tag):
		Buff.__init__(self)
		self.name = "Orders"
		self.stack_type = STACK_REPLACE
		self.buff_type = BUFF_TYPE_BLESS
		self.show_effect = False
		self.asset = ["TcrsCustomModpack", "Misc", "orders_buff"]
		self.tag = tag
		self.color = tag.color
		self.owner_triggers[EventOnSpellCast] = self.on_cast
		self.skill = skill

	def on_cast(self, evt):
		if self.tag in evt.spell.tags:
			for i in range(self.skill.get_stat('num_summons')):
				unit = copy.deepcopy(self.skill.tagdict[self.tag][1])
				grant_minion_spell(copy.deepcopy(self.skill.tagdict[self.tag][0]), unit, self.owner)
				unit.apply_buff(LivingScrollSuicide())
				self.summon(unit, sort_dist=False)

class Orders(Upgrade):
	def on_init(self):
		self.name = "Orders"
		self.tags = [Tags.Sorcery]
		self.level = 4
		self.asset = ["TcrsCustomModpack", "Icons", "orders"]

		self.minion_health = 5
		self.num_summons = 2
		self.duration = 1
		
		self.tagdict = ScrollConvertor()

	def get_description(self):
		return ("Each turn gain the Orders buff, which has a random tag. It can be: [Fire], [Lightning], [Ice], [Nature], [Arcane], [Dark], [Holy], or [Blood].\n"
				"When you cast a spell with that tag, summon [{num_summons}:num_summons] living scrolls which cast your corresponding cantrip. The buff lasts 1 turn.").format(**self.fmt_dict())

	def on_advance(self): ##Add metallic and chaos cantrips
		tag = random.choice([Tags.Fire, Tags.Lightning, Tags.Ice, Tags.Nature, Tags.Arcane, Tags.Dark, Tags.Holy, Tags.Blood])
		buff = OrdersBuff(self, tag)
		buff.name = tag.name + " Orders"
		self.owner.apply_buff(buff, self.get_stat('duration'))


class Mechanize(Upgrade):
	def on_init(self):
		self.name = "Mechanize"
		self.level = 5
		self.tags = [Tags.Metallic]
		self.asset = ["TcrsCustomModpack", "Icons", "mechanize"]
		self.description = "When a [metallic] ally dies, a random ally gains 50% of the unit's max hp, and if non-metallic gains the [metallic] tag and resistances."

		self.global_triggers[EventOnDeath] = self.on_death
	
	def on_death(self, evt):
		if Tags.Metallic not in evt.unit.tags:
			return
		units = [u for u in self.owner.level.units if not u.is_player_controlled and not are_hostile(u, self.owner)]
		if units == []:
			return
		unit = random.choice(units)
		bonus = evt.unit.max_hp // 2
		unit.max_hp += bonus
		unit.cur_hp += bonus
		if Tags.Metallic not in unit.tags:
			BossSpawns.apply_modifier(BossSpawns.Metallic, unit)


class SlimeCantripEducation(Spell):
	def on_init(self):
		self.name = "Slime Education"
		self.description = "Grants one slime within 8 tiles a random level 1 sorcery. Does not pick slimes which already have 2 or more spells."
		self.range = 0
		self.cool_down = 2
		self.radius = 8
		
	def get_nearby_slimes(self, x, y):
		slimes = [u for u in self.caster.level.get_units_in_ball(Point(x, y), self.get_stat('radius')) if not are_hostile(u, self.caster) and Tags.Slime in u.tags and u != self.caster and len(u.spells) < 2]
		if slimes == []:
			return None
		return slimes

	def can_cast(self, x, y):
		slimes = self.get_nearby_slimes(x, y)
		if slimes == None:
			return False
		else:
			return Spell.can_cast(self, x, y)

	def get_ai_target(self):
		slimes = self.get_nearby_slimes(self.owner.x, self.owner.y)
		if slimes == None:
			return None
		else:
			return self.caster

	def cast(self, x, y):
		slimes = self.get_nearby_slimes(x, y)
		if not slimes:
			return
		slime = random.choice(slimes)
		
		cantrips = [Spells.FireballSpell, Spells.Icicle, Spells.LightningBoltSpell, Spells.PoisonSting, Spells.MagicMissile, Spells.DeathBolt, MetalShard, Improvise]
		spell = random.choice(cantrips)()
		spell.statholder = slime
		spell.caster = slime
		spell.owner = slime
		
		slime.spells.insert(0, spell)
		yield

def LearnedSlime():
	unit = Unit()
	unit.name = "Slime Scholar"
	unit.max_hp = 10
	unit.tags = [Tags.Slime]
	unit.asset = ["TcrsCustomModpack", "Units", "slime_scholar"]

	unit.spells.append(SlimeCantripEducation())
	unit.buffs.append(SlimeBuff(spawner=LearnedSlime))

	unit.resists[Tags.Poison] = 100
	return unit

class SlimeScholar(Upgrade):
	def on_init(self):
		self.name = "Slime Scholar"
		self.level = 5
		self.tags = [Tags.Arcane, Tags.Sorcery, Tags.Conjuration, Tags.Slime]
		self.asset = ["TcrsCustomModpack", "Icons", "slime_scholar_icon"]
		
		self.global_triggers[EventOnUnitAdded] = self.on_unit_enter
		self.count = 0
		self.threshold = 100
		self.minion_health = 10

	def get_description(self):
		return ("When allied slimes are summoned, including by splitting, gain 1 Oozing Knowledge for each max hp it has.\n"
				"Each turn, consume up to 100 Oozing Knowledge to summon a slime scholar, which can teach a slime a random cantrip, but only if it has less than 2 spells.\n"
				"Oozing Knowledge: %d\n" % self.count)

	def get_extra_examine_tooltips(self):
		return [LearnedSlime()]

	def on_advance(self):
		if self.count < self.threshold:
			return
		self.count -= self.threshold
		unit = LearnedSlime()
		apply_minion_bonuses(self, unit)
		self.summon(unit, radius=1)

	def on_unit_enter(self, evt):
		if evt.unit == self.owner:
			self.count = 0
			self.threshold = 100
		if Tags.Slime in evt.unit.tags and not are_hostile(self.owner, evt.unit):
			self.count += evt.unit.max_hp



class Agoraphobia(Upgrade):  ##Possible crash from this. Hard to tell what happened.
	def on_init(self):
		self.name = "Agoraphobia"
		self.level = 5
		self.asset = ["TcrsCustomModpack", "Icons", "agoraphobia"]
		
		self.tags = [Tags.Enchantment, Tags.Eye]
		self.damage = 15

	def get_description(self):
		return ("If you have 6 or more walls surrounding you, deal [{damage}_damage:damage] to one random enemy for each eye buff you have."
				"\nThe damage type is the same as your eye buff, and Eye of Rage deals poison damage.").format(**self.fmt_dict())

	def on_advance(self): ##TODO Probably can implement this as a queued spell for readability.
		count = 0
		tiles = self.owner.level.get_points_in_rect(self.owner.x-1, self.owner.y-1, self.owner.x+1, self.owner.y+1)
		for t in tiles:
			if self.owner.level.tiles[t.x][t.y].is_wall():
				count += 1
		if count < 6:
			return
		possible_targets = self.owner.level.units
		possible_targets = [t for t in possible_targets if self.owner.level.are_hostile(t, self.owner)]
		# visible_targets = [t for t in possible_targets if self.owner.level.can_see(t.x, t.y, self.owner.x, self.owner.y)]
		# if not visible_targets == []:
		# 	return
		targets = [t for t in possible_targets if not self.owner.level.can_see(t.x, t.y, self.owner.x, self.owner.y)]
		if targets == []:
			return
		for b in self.owner.buffs:
			if isinstance(b, Spells.ElementalEyeBuff):
				if possible_targets:
					if isinstance(b, RageEyeBuff): ##Should work with the holy damage from Opalescent Eyes.
						element = Tags.Poison
					else:
						element = b.element
					res_targets = [t for t in possible_targets if t.resists[element] < 100]
					if res_targets == []:
						continue
					target = random.choice(res_targets)
					self.owner.level.deal_damage(target.x, target.y, self.get_stat('damage'), element, self)


class BloodBagBuff(Buff):
	def __init__(self, amount):
		self.amount = amount
		self.description = "Hemostasis: " + str(self.amount)
		Buff.__init__(self)	

	def on_init(self):
		self.color = Tags.Blood.color
		self.name = "Hemostasis"
		self.description = "Reduce the hp cost of your next blood spell."
		self.owner_triggers[EventOnSpellCast] = self.on_cast
		
	def on_applied(self, owner):
		for s in self.owner.spells:
			if Tags.Blood not in s.tags:
				continue
			if s.hp_cost and s.hp_cost <= self.amount:
				self.spell_bonuses[type(s)]['hp_cost'] = s.hp_cost * -1
			else:
				self.spell_bonuses[type(s)]['hp_cost'] = self.amount * -1
		if self.amount > 0:
			self.name = "Hemostasis:" + str(self.amount)


	def on_cast(self, evt):
		if not evt.pay_costs:
			return
		if Tags.Blood in evt.spell.tags and evt.spell.hp_cost:
			self.amount -= evt.spell.hp_cost
			if self.amount <= 0:
				self.owner.remove_buff(self)
				return
			duration = self.turns_left
			self.owner.remove_buff(self)
			self.owner.apply_buff(BloodBagBuff(self.amount), duration)


class ForcedDonation(Upgrade):
	def on_init(self):
		self.name = "Blood Drive"
		self.level = 6
		self.asset = ["TcrsCustomModpack", "Icons", "forced_donation"]
		self.tags = [Tags.Blood]
		
		self.radius = 1
		self.duration = 10

	def get_description(self):
		return ("Each turn, you drain the hp of one [living] or [demon] enemy unit within [{radius}_tiles:radius]. This is not damage and cannot be resisted. "
				"The drain amount is the total hp cost of all blood spells you know.\n"
				" Gain Hemostasis, causing blood spells to not pay hp costs, up to the amount of hp drained."
				" The Buff lasts [{duration}_turns:duration], and is reduced by any hp costs paid with the buff.\n"
				"If applied more than once, the buffs combine their total value.").format(**self.fmt_dict())

	def on_advance(self):
		hp_cost_total = 0
		for s in self.owner.spells:
			if s.hp_cost > hp_cost_total:
				hp_cost_total += s.hp_cost
		if hp_cost_total == 0:
			return

		units = self.owner.level.get_units_in_ball(Point(self.owner.x, self.owner.y), self.get_stat('radius'), diag=True)
		units = [u for u in units if (Tags.Living in u.tags or Tags.Demon in u.tags) and are_hostile(self.owner, u)]
		if units == []:
			return

		target = random.choice(units)
		amount_drained = target.cur_hp 
		target.cur_hp -= hp_cost_total
		self.owner.level.show_effect(target.x, target.y, Tags.Blood, minor=False)
		if target.cur_hp <= 0:
			target.kill()
		if hp_cost_total < amount_drained:
			amount_drained = hp_cost_total
			
		prev_buff = self.owner.get_buff(BloodBagBuff)
		if prev_buff != None:
			amount_drained += prev_buff.amount
			self.owner.remove_buff(prev_buff)
		self.owner.apply_buff(BloodBagBuff(amount_drained), self.get_stat('duration'))


def IceShambler(HP=1):
	unit = Unit()
	unit.max_hp = HP
	unit.tags = [Tags.Elemental, Tags.Ice, Tags.Undead]
	unit.resists[Tags.Ice] = 100
	unit.resists[Tags.Fire] = -100

	if HP >= 64:
		unit.name = "Iceberg Shambler"
		unit.asset = ["TcrsCustomModpack", "Units", "ice_shambler_large"]
		unit.spells.append(SimpleRangedAttack(damage=16, range=4, damage_type=Tags.Ice, buff=FrozenBuff, buff_duration=1))
	elif HP >= 8:
		unit.name = "Ice Shambler"
		unit.asset = ["TcrsCustomModpack", "Units", "ice_shambler_med"]
		unit.spells.append(SimpleRangedAttack(damage=8, range=3, damage_type=Tags.Ice, buff=FrozenBuff, buff_duration=1))
	else:
		unit.name = "Icicle Shambler"
		unit.asset = ["TcrsCustomModpack", "Units", "ice_shambler_small"]
		unit.spells.append(SimpleRangedAttack(damage=4, range=2, damage_type=Tags.Ice, buff=FrozenBuff, buff_duration=1))

	unit.description = "Jagged ice and marrow given unlife."
	if HP >= 8:
		unit.description += "  Splits into 4 smaller Ice Shamblers upon death."
		unit.buffs.append(SplittingBuff(spawner=lambda : IceShambler(unit.max_hp // 4), children=4))
		
	return unit

def IceShambler_Big(HP=64):
	return IceShambler(64)

def IceShambler_Med(HP=8):
	return IceShambler(8)

class IcyShambler(Upgrade):
	def on_init(self):
		self.name = "Shambling Frostspawn"
		self.level = 7
		self.tags = [Tags.Ice, Tags.Dark, Tags.Conjuration]
		self.asset = ["TcrsCustomModpack", "Icons", "ice_shambler_icon"]
		
		self.global_triggers[EventOnDeath] = self.on_death
		self.owner_triggers[EventOnUnitAdded] = self.on_enter
		
		self.minion_life = 1
		self.minion_range = 4
		self.minion_damage = 16
		self.num_summons = 3
		self.summon_cap = 0
		self.count = 0
		self.max_hp = 0

	def get_description(self):
		return ("After 6 [Ice] or [Undead] minions die, summon an icy shambler with their total max hp. Each realm can trigger this effect [{num_summons}:num_summons] times.").format(**self.fmt_dict())

	def get_extra_examine_tooltips(self):
		return [IceShambler(1), IceShambler_Med(8), IceShambler_Big(64)]

	def on_enter(self, evt):
		self.count = 0
		self.summon_cap = 0
		self.max_hp = 0

	def on_death(self, evt):
		if are_hostile(self.owner, evt.unit):
			return
		if Tags.Ice not in evt.unit.tags and Tags.Undead not in evt.unit.tags:
			return
		if self.summon_cap == self.get_stat('num_summons'):
			return
		self.count += 1
		self.max_hp += evt.unit.max_hp
		if self.count == 6:
			self.summon_cap += 1
			self.count = 0
			unit = IceShambler(self.max_hp)
			apply_minion_bonuses(self, unit)
			unit.max_hp = self.max_hp
			self.summon(unit=unit, target=Point(self.owner.x, self.owner.y))
			self.max_hp = 0


class SixthSenseBuff(Buff):
	def __init__(self, skill):
		self.skill = skill
		Buff.__init__(self)
	def on_init(self):
		self.buff_type = BUFF_TYPE_BLESS
		self.color = Tags.Eye.color
		self.global_bonuses['requires_los'] = -1
		self.global_bonuses['range'] = self.skill.get_stat('range')
		self.description = "May cast spells without line of sight"
		self.name = "Sixth Sense"

class SixthSense(Upgrade):
	def on_init(self):
		self.name = "Sixth Sense"
		self.level = 6
		self.tags = [Tags.Enchantment, Tags.Eye]
		self.asset = ["TcrsCustomModpack", "Icons", "sixth_sense"] ##Oculus + eye of thunder shrunk down and recoloured.
		self.owner_triggers[EventOnSpellCast] = self.on_spell_cast
		self.count_turn = 6
		self.count_spell = 6
		self.range = 2

	def get_description(self):
		return ("After 6 eye spells are cast or when 6 turns pass, gain sixth sense for 1 turn.\n"
				"Sixth Sense grants your spells [2:range] bonus range and removes the line of sight requirement.\n"
				"Turns Remaining: %d\n"
				"Spells Remaining: %s"% (self.count_turn, self.count_spell)).format(**self.fmt_dict())

	def on_advance(self):
		self.count_turn -= 1
		if self.count_turn <= 0:
			self.owner.apply_buff(SixthSenseBuff(self), 1)
			self.count_turn = 6
			
	def on_spell_cast(self, evt):
		if Tags.Eye not in evt.spell.tags:
			return
		self.count_spell -= 1
		if self.count_spell <= 0:
			self.owner.apply_buff(SixthSenseBuff(self), 2)
			self.count_spell = 6


class SpeakerForDead(Upgrade):
	def on_init(self):
		self.name = "Speaker for the Dead"
		self.level = 6
		self.tags = [Tags.Dark, Tags.Word]
		self.asset = ["TcrsCustomModpack", "Icons", "speaker_for_dead"] ##Slightly modified skeleton and bone wizard
		self.cur_charges = 1
		self.count = 15
		self.global_triggers[EventOnDeath] = self.on_death
		self.owner_triggers[EventOnUnitAdded] = self.on_enter
		
		self.description = ("For every 15 [undead] units that die, cast one of your [word] spells for free. If you don't know any [word] spells, cast word of undeath." +
							"\nThis skill's charges refresh when you enter a new realm.\nCharges: " + str(self.cur_charges) + " Remaining Undead: " + str(self.count)).format(**self.fmt_dict())

	def update_desc(self):
		self.description = ("For every 15 [undead] units that die, cast one of your [word] spells for free. If you don't know any [word] spells, cast word of undeath." +
							"\nThis skill's charges refresh when you enter a new realm.\nCharges: " + str(self.cur_charges) + " Remaining Undead: " + str(self.count)).format(**self.fmt_dict())

	def on_enter(self, evt):
		self.count = 15
		word_charges = self.owner.tag_bonuses[Tags.Word]['max_charges'] * (1 + self.owner.tag_bonuses_pct[Tags.Word]['max_charges'])
		dark_charges = self.owner.tag_bonuses[Tags.Dark]['max_charges'] * (1 + self.owner.tag_bonuses_pct[Tags.Dark]['max_charges'])
		self.cur_charges = word_charges + dark_charges
		self.update_desc()

	def on_death(self, evt):
		if not Tags.Undead in evt.unit.tags:
			return
		if self.cur_charges <= 0:
			return
		self.count -= 1
		if self.count > 0:
			return
		self.update_desc()
		self.count = 15
		word_spells = []
		for s in self.owner.spells:
			if Tags.Word in s.tags:
				word_spells.append(s)
		if self.cur_charges < 1:
			return
		self.cur_charges -= 1
		self.update_desc()
		if word_spells == []:
			word = self.owner.get_or_make_spell(WordOfUndeath)
		else:
			random.shuffle(word_spells)
			word = self.owner.get_or_make_spell(type(word_spells[0]))
		self.owner.level.act_cast(self.owner, word, self.owner.x, self.owner.y, pay_costs=False)

class NarrowSouled(Upgrade):
	def on_init(self):
		self.name = "Narrow Souled"
		self.level = 4
		self.tags = [Tags.Arcane, Tags.Dark, Tags.Chaos]
		self.asset = ["TcrsCustomModpack", "Icons", "narrow_souled"] ##Soul tax recolour + aether dagger colours.
		self.trigger = False
		self.owner_triggers[EventOnSpellCast] = self.on_cast
		self.owner_triggers[EventOnUnitAdded] = self.on_enter
		self.description = ("On the 4th turn of each realm if you cast an [arcane] spell, you also use an Aether Dagger item.\n" +
							"This happens for the 6th turn with a [dark] spell, and the Death Dice item, and the 8th turn with a [chaos] spell, and the Chaos Bell item." +
							"\nYou can only trigger this effect once per realm.").format(**self.fmt_dict())
	
	def on_enter(self, evt):
		self.trigger = False

	def on_cast(self, evt):
		turn = self.owner.level.turn_no
		if self.trigger == True:
			return
		if not (Tags.Arcane in evt.spell.tags or Tags.Dark in evt.spell.tags or Tags.Chaos in evt.spell.tags):
			return
		
		spell = None
		if Tags.Arcane in evt.spell.tags and turn == 4:
			spell = AetherDaggerSpell()
			spell.on_init()
			spell.name = "Aether Dagger"
		if Tags.Dark in evt.spell.tags and turn == 6:
			spell = DeathDiceSpell()
			spell.on_init()
			spell.name = "Death Dice"
		if Tags.Chaos in evt.spell.tags and turn == 8:
			spell = ChaosBellSpell()
			spell.on_init()
			spell.name = "Chaos Bell"

		if spell == None:
			return
		spell.owner = self.owner
		spell.caster = self.owner
		spell.item = True
		self.trigger = True
		self.owner.level.act_cast(self.owner, spell, self.owner.x, self.owner.y, pay_costs=False)


class FireBreathing(Upgrade):
	def on_init(self):
		self.name = "Chromatic Breath"
		self.level = 4
		self.tags = [Tags.Dragon, Tags.Enchantment]
		self.asset = ["TcrsCustomModpack", "Icons", "chromatic_breath"] ##Player + recoloured dragon breath sprite
		self.owner_triggers[EventOnBuffApply] = self.on_buff	
		self.range = 7
		self.description = ("Once per turn, when you are inflicted by a debuff, you use a breath weapon on a random enemy within [{range}_tiles:range]."
							"\nThe breath is randomly chosen from your dragon spells which have a breath weapon.").format(**self.fmt_dict())
		self.dragon_dict = {SummonFireDrakeSpell:FireBreath, SummonStormDrakeSpell:StormBreath, SummonIceDrakeSpell:IceBreath, 
							SummonVoidDrakeSpell:VoidBreath, SummonGoldDrakeSpell:HolyBreath, WyrmEggs:random.choice([FireBreath, IceBreath]),
							SeaSerpent:SeaWyrmBreath, SummonEyedra:VoidBreath, SteelFangs:ShrapnelBreath,
							SummonFrostfireHydra:random.choice([FireBreath, IceBreath]), SummonBookwyrm:ScrollBreath}

	def on_buff(self, evt):
		if not evt.buff.applied:
			return
		if evt.buff.buff_type != BUFF_TYPE_CURSE: ##Doesn't include soaked, should it? Very easy to apply.
			return
		spells = [s for s in self.owner.spells if Tags.Dragon in s.tags and hasattr(s, 'minion_damage')]
		if spells == []:
			return
		spell = random.choice(spells)
		if type(spell) not in self.dragon_dict:
			print("not found")
			breath = random.choice([FireBreath, IceBreath, StormBreath, VoidBreath, HolyBreath])
		else:
			breath = self.dragon_dict[type(spell)]()
		breath.item = False
		breath.source = self
		breath.caster = self.owner
		breath.statholder = self.owner
		breath.owner = self.owner
		breath.name = "Chromatic Breath"
		targets = self.owner.level.get_units_in_ball(self.owner, self.get_stat('range'))
		targets = [t for t in targets if are_hostile(self.owner, t)]
		if targets == []:
			return
		random.shuffle(targets)
		target = targets[0]
		self.owner.level.act_cast(self.owner, breath, target.x, target.y, pay_costs=False, queue=True)


class VowOfPoverty(Upgrade):
	def on_init(self):
		self.name = "Vow of Poverty"
		self.level = 4
		self.tags = [Tags.Holy]
		self.owner_triggers[EventOnUnitAdded] = self.on_enter
		self.asset = ["TcrsCustomModpack", "Icons", "vow_of_poverty"]
		self.description = ("When you enter a realm, if you have 3 or fewer types of items, produce a random item in an adjacent tile.\n"
							"If you enter a realm with 4 or more types of items, lose all but your first 3 types and gain 10 max hp per item type lost.")
		
	def on_enter(self, evt):
		items = self.owner.items
		if len(items) <= 3:
			point = Point(self.owner.x, self.owner.y)
			adj_point = None
			rect = list(self.owner.level.get_points_in_rect(point.x - 1, point.y - 1, point.x + 1, point.y + 1))
			random.shuffle(rect)
			for p in rect:
				if not self.owner.level.tiles[p.x][p.y].prop and self.owner.level.tiles[p.x][p.y].is_floor():
					adj_point = Point(p.x, p.y)
					break
			if adj_point == None:
				return
			point = adj_point
			item = roll_consumable()
			prop = ItemPickup(item)
			self.owner.level.add_prop(prop, point.x, point.y)

		elif len(items) > 3:
			index = 0
			for i in range(len(items)): ## Horrid case of manipulating list length while iterating through it. Do not do this ever.
				if i > 2:
					self.owner.remove_item(self.owner.items[index])
					self.owner.max_hp += 10
				else:
					index += 1


class RenouncedEvil(Buff):
	def __init__(self, count):
		self.count = count
		Buff.__init__(self)
	
	def on_init(self):
		self.name = "Renounce Darkness"
		self.color = Tags.Holy.color
		self.buff_type = BUFF_TYPE_BLESS
		self.tag_bonuses[Tags.Holy]['damage'] = self.count
		self.tag_bonuses[Tags.Nature]['damage'] = self.count

class RenounceDarkness(Upgrade):
	def on_init(self):
		self.name = "Renounce Darkness"
		self.level = 5
		self.tags = [Tags.Holy, Tags.Nature]
		self.asset = ["TcrsCustomModpack", "Icons", "renounce_darkness"] #Modified Warlock
		
		self.resists[Tags.Dark] = 25
		self.owner_triggers[EventOnUnitAdded] = self.on_enter
		self.description = ("At the start and end of each turn, transfer charges from your [dark], [chaos], and [blood] spells to your [holy] and [nature] spells. " +
		"Transfers 33% of the charges, rounded down, to the first [nature] or [holy] spell of the same or lower level in your spells." +
		"\nWhen you enter a realm gain +1 [holy] and [nature] damage for each level of those spells you have.")

	def charge_transfer(self):
		dcb_spells = [s for s in self.owner.spells if Tags.Dark in s.tags or Tags.Chaos in s.tags or Tags.Blood in s.tags]
		hn_spells = [s for s in self.owner.spells if (Tags.Holy in s.tags or Tags.Nature in s.tags) and s not in dcb_spells]
		for s in dcb_spells:
			if s.cur_charges == 0:
				continue
			count = s.cur_charges
			s.cur_charges = 0
			for recipient in hn_spells:
				if recipient.level <= s.level:
					recipient.cur_charges += count // 3
					continue

	def on_enter(self, evt):
		self.charge_transfer()
		count = 0
		for s in self.owner.spells:
			if Tags.Dark in s.tags or Tags.Chaos in s.tags or Tags.Blood in s.tags:
				count += s.level
		self.owner.apply_buff(RenouncedEvil(count))
		count = 0

	def on_advance(self):
		self.charge_transfer()
	
	def on_pre_advance(self):
		self.charge_transfer()

	# def on_pre_advance(self):
	# 	for s in self.owner.spells:
	# 		if s.cur_charges == 0:
	# 			continue
	# 		if Tags.Dark in s.tags or Tags.Chaos in s.tags or Tags.Blood in s.tags:
	# 			s.cur_charges = 0
				

class OnewithNothing(Upgrade):
	def on_init(self):
		self.name = "One With Nothing"
		self.tags = [Tags.Arcane]
		self.level = 4
		self.owner_triggers[EventOnUnitAdded] = self.on_enter
		self.damage = 1
		self.description = "Before your turn gain a 1 damage arcane melee attack if you don't have one already.\nFor each spell you know which currently has 0 charges, give 1 damage to your melee spell. Reset each realm."

	def on_enter(self, evt):
		spell = self.owner.melee_spell
		spell.damage = 1

	def on_pre_advance(self):
		spell = self.owner.melee_spell
		if spell == None:
			spell = SimpleMeleeAttack(damage=self.get_stat('damage'))
			spell.owner = self.owner
			spell.caster = self.owner
			spell.tags = [Tags.Arcane]
			self.owner.melee_spell = spell
		for s in self.owner.spells:
			if s.cur_charges == 0:
				spell.damage += 1
		

class DazzlingMovement(Upgrade):
	def on_init(self):
		self.name = "Dazzling Movement"
		self.level = 4
		self.tags = [Tags.Holy, Tags.Translocation]
		self.owner_triggers[EventOnMoved] = self.on_move
		self.asset = ["TcrsCustomModpack", "Icons", "dazzling_movement"]
		
		self.damage = 10
		self.charges = 0
		self.radius = 10
		self.moved = True

	def get_description(self):
		return ("Each time that you move, gain a charge. Teleporting grants 2 charges.\n"
				"On a turn that you don't move, consume all charges to deal damage in a burst, growing by 1 tile for every 2 charges.\n"
				"The burst deals [{damage}_holy:holy] with a [{radius}_tile:radius] tiles at max charges."
				" %d charges" % self.charges).format(**self.fmt_dict())

	def on_move(self, evt):
		if evt.teleport == True:
			self.charges += 2
		else:
			self.charges += 1
		if self.charges > self.radius * 2:
			self.charges = self.radius * 2
		self.moved = True
		
	def on_advance(self):
		if self.charges == 0:
			return
		if self.moved:
			self.moved = False
			return
		radius = math.floor(self.charges / 2)
		for stage in Burst(self.owner.level, self.owner, radius):
			for point in stage:
				if point.x == self.owner.x and point.y == self.owner.y:
					continue
				self.owner.level.deal_damage(point.x, point.y, self.get_stat('damage'), Tags.Holy, self)
		self.charges = 0
		self.moved = False

class Basics(Upgrade):
	def on_init(self):
		self.name = "Practice the Basics"
		self.level = 4
		self.tags = [Tags.Sorcery]
		self.owner_triggers[EventOnSpellCast] = self.on_cast
		self.global_triggers[EventOnLevelComplete] = self.on_complete
		self.description = "This skill gains 1 [Sorcery] damage permanently for each realm completed. It loses 1 bonus damage if you cast any level 2 or higher spell."
		self.asset = ["TcrsCustomModpack", "Icons", "dazzling_movement"] ##TODO Asset
		self.spell_level = 1
		self.tag_bonuses[Tags.Sorcery]['damage'] = 1
		
	def on_cast(self, evt):
		print(evt.spell.level)
		if evt.spell.level > self.spell_level:
			self.spell_level = evt.spell.level
			if self.tag_bonuses[Tags.Sorcery]['damage'] > 0:
				self.tag_bonuses[Tags.Sorcery]['damage'] -= 1
				self.owner.tag_bonuses[Tags.Sorcery]['damage'] -= 1

	def on_complete(self, evt):
		if self.spell_level > 1:
			self.spell_level = 1
			return
		
		self.spell_level = 1
		self.tag_bonuses[Tags.Sorcery]['damage'] += 1
		self.owner.tag_bonuses[Tags.Sorcery]['damage'] += 1

def SilverGorgon():
	unit = GreenGorgon()
	breath = ShrapnelBreath()
	breath.damage = 8
	unit.spells = [breath]
	unit.tags = [Tags.Holy, Tags.Metallic, Tags.Living]
	return unit

class SilverGorgonFamiliar(Upgrade):
	def on_init(self):
		self.level = 5
		self.tags = [Tags.Holy, Tags.Metallic, Tags.Conjuration]
		self.name = "Silver Gorgon"
		
		self.unit = None
		self.counter_max = 5
		self.counter = self.counter_max
		self.owner_triggers[EventOnUnitAdded] = self.on_enter_level
		self.global_triggers[EventOnDeath] = self.on_death

		self.minion_health = 66
		self.minion_damage = 8

	def get_description(self):
		return ("After 5 units die from [physical] or [holy] damage, summon a silver gorgon familiar if you do not currently have one.\n"
				"The familiar has [{minion_health}_health:minion_health] and a [physical] breath attack which deals [{minion_damage}_damage:minion_damage].\n"
				"It can cast your: Metal Shard, Mercurize, Ironize, Heavenly Blast, Scourge, and Holy Armor spells on a 3 turn cooldown.\n").format(**self.fmt_dict())

	def on_enter_level(self, evt):
		self.counter = self.counter_max

	def on_death(self, evt):
		if evt.damage_event == None:
			return
		if not (evt.damage_event.damage_type == Tags.Holy or evt.damage_event.damage_type == Tags.Physical):
			return
		if not self.has_unit():
			self.counter -= 1
			if self.counter <= 0:
				self.summon_gorgon()
				self.counter = self.counter_max

	def summon_gorgon(self):
		self.unit = self.make_gorgon()
		apply_minion_bonuses(self, self.unit)
		self.summon(self.unit)

	def has_unit(self):
		return self.unit and self.unit.is_alive() and self.unit.level == self.owner.level ##Interesting check in the original skill


	def make_gorgon(self):
		monster = SilverGorgon()

		allowed_spells = [
			MetalShard,
			MercurizeSpell,
			ProtectMinions,
			HolyBlast,
			ScourgeSpell,
			HolyShieldSpell
		]


		for spell in reversed(self.owner.spells):
			if type(spell) in allowed_spells:
				temp_spell = type(spell)()
				temp_spell.statholder = self.owner
				temp_spell.max_charges = 0
				temp_spell.cur_charges = 0
				temp_spell.cool_down = 3
				temp_spell.description = "\n"
				monster.spells.insert(0, temp_spell)

		return monster

class StolenTime(Buff):
	def on_init(self):
		self.name = "Stolen Time"
		self.color = Tags.Arcane.color
		self.buff_type = BUFF_TYPE_BLESS
		self.tag_bonuses[Tags.Arcane]['quick_cast'] = 1
		self.tag_bonuses[Tags.Lightning]['quick_cast'] = 1
		self.owner_triggers[EventOnSpellCast] = self.on_cast
			
	def on_pre_advance(self):
		if self.owner.moves_left == 0:
			self.owner.moves_left += 1

	def on_cast(self,evt):
		if Tags.Arcane in evt.spell.tags or Tags.Lightning in evt.spell.tags:
			self.owner.level.queue_spell(self.clear_buffs())
			
	def clear_buffs(self):
		self.owner.remove_buff(self)
		yield

class ThiefOfTime(Upgrade):
	def on_init(self):
		self.level = 6
		self.tags = [Tags.Arcane, Tags.Lightning]
		self.name = "Thief of Time"
		self.description = ("Each turn, steal 1 turn from all unit's buffs, and 1 turn from all units which are temporary.\n"
							"Every 10 turns that are stolen, gain Stolen Time for 5 turns, granting you 1 free tile moved per turn and quickcast to your next [arcane] or [lightning] spell."
							"Removed on casting an [arcane] or [lightning] spell.")
		self.stolen_turns = 0

	def on_advance(self):
		units = self.owner.level.units
		temp_units = [u for u in units if u.turns_to_death != None]
		for u in temp_units:
			if u.turns_to_death <= 1:
				continue
			u.turns_to_death -= 1
			self.stolen_turns += 1
			if u.turns_to_death == 0:
				u.kill()
				
		buff_units = [u for u in units if u.buffs != []]
		for u in buff_units:
			for b in u.buffs:
				if b.buff_type == BUFF_TYPE_BLESS or b.buff_type == BUFF_TYPE_CURSE:
					if b.turns_left > 1:
						self.stolen_turns += 1
						b.turns_left -= 1
						
		if self.stolen_turns >= 10:
			self.stolen_turns -= 10
			self.owner.apply_buff(StolenTime(), 5)


class DirectionalOrders(Buff):
	def __init__(self, skill, point, direction):
		self.skill = skill
		self.point = point
		self.direction = direction
		Buff.__init__(self)
		
	def on_init(self):
		self.name = "Move! " + self.direction
		self.color = Tags.Translocation.color
		self.buff_type = BUFF_TYPE_BLESS
		self.stack_type = STACK_REPLACE
		self.show_effect = False
		self.owner_triggers[EventOnMoved] = self.on_move
		self.count = 0
			
	def on_move(self, evt):
		if self.direction == "Left" and self.point.x > self.owner.x:
			self.skill.count +=1
		elif self.direction == "Right" and self.point.x < self.owner.x:
			self.skill.count +=1
		elif self.direction == "Up" and self.point.y > self.owner.y:
			self.skill.count +=1
		elif self.direction == "Down" and self.point.y < self.owner.y:
			self.skill.count +=1
		else:
			self.skill.count = 0


class StratagemPriority(Upgrade):
	def on_init(self):
		self.name = "Confusing Strategy"
		self.level = 0
		self.tags = [Tags.Translocation, Tags.Chaos]
		self.damage = 1
		self.count = 0

	def get_description(self):
		return ("Before your turn gain Confusing Strategy, which indicates a direction.\nWhen your turn ends if you have moved towards that direction, gain a charge.\n"
				"Every 5 charges, deal {damage} [Fire], [Lightning], or [Physical] damage to all enemies, and apply Berserk for 2."
				"\nCharges: %d" % self.count).format(**self.fmt_dict())

	def on_pre_advance(self):
		if self.count >= 4:
			self.count = 0
			eligible_units = [u for u in self.owner.level.units if are_hostile(u, self.owner)]
			if eligible_units:
				for u in eligible_units:
					tag = random.choice([Tags.Fire, Tags.Lightning, Tags.Physical])
					u.deal_damage(self.get_stat('damage'), tag, self)
					u.apply_buff(BerserkBuff(), 2)
					
		direction = random.choice(["Left", "Right", "Up", "Down"])
		self.owner.apply_buff(DirectionalOrders(self, Point(self.owner.x, self.owner.y), direction), 1)

## ------------------------------------------ TODO Implementation Zone -------------------------------------------------------


def construct_skills():
	skillcon = [FromAshes, Lucky13, PsionicBlast, Crescendo, Librarian, BoneShaping, Chiroptyvern, Condensation, Discharge, PoisonousCopy, 
				IcyVeins, HolyMetalLantern, NightsightLantern, ContractFromBelow, MageArmor, Friction, Accelerator, ArclightEagle, Scrapheap, WeaverOfElements,
				WeaverOfOccultism, WeaverOfMaterialism, Mathemagics, QueenOfTorment, Cloudcover, WalkTheOrb, EyeSpellTrigger, Overheal, RimeorbLantern,
				ChaosScaleLantern, AuraReading, Hindsight, Pleonasm, Triskadecaphobia, VoidCaller, OrbWeaver, LightningReflexes, TheFirstSeal, ChaosLord,
				DarkBargain, TheHitList, ArcticPoles, Overkill, Recyclone, Orders, Mechanize, SlimeScholar, Agoraphobia, ForcedDonation, IcyShambler,
				SixthSense, SpeakerForDead, NarrowSouled, FireBreathing, VowOfPoverty, RenounceDarkness, DazzlingMovement, Basics, SilverGorgonFamiliar,
				ThiefOfTime, StratagemPriority]
	
	## AngularGeometry OneWithNothing
	print("Added " + str(len(skillcon)) + " skills")
	for s in skillcon:
		Upgrades.skill_constructors.extend([s])

