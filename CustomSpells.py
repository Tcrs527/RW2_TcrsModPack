from os import listdir
import queue
import sys
import os.path

from Variants import BagOfBugsBrain, BrainFlies
from RareMonsters import BoxOfWoe
sys.path.append('../..')

import Spells
import Equipment as Equip
from Game import *
from Level import *
from Monsters import *
from copy import copy, deepcopy
import math
import itertools
import BossSpawns


from mods.TcrsCustomModpack.SharedClasses import *

print("Custom Spells Loaded")


##Implement stored impact_tile / targetable tile variables so it doesn't redraw it a billion times a second?
##TODO	Fix Flywheel's one missing pixel
##		Make the earliest icons like metal shard not use the old style icon which flashes between 7 frames
##		Use raise_elemental (CommonContent.py) to do something cool.
##TODO determine if minion_duration -> permanent minions causing them to have a lifetime is affecting any permanent minions in vanilla

water_tag = Tag("Water", Color(14,14,250)) ##Purely for cross-mod compatibility

class Improvise(Spell):
	def on_init(self):
		self.name = "Improvise"
		self.asset = ["TcrsCustomModpack", "Icons", "improvise"]
		self.tags = [Tags.Chaos, Tags.Sorcery, Tags.Conjuration]
		self.level = 1
		
		self.damage = 7
		self.damage_type = [Tags.Physical, Tags.Fire, Tags.Lightning]
		self.max_charges = 21
		self.range = 5
		self.minion_health = 7
		self.minion_duration = 7
		self.minion_damage = 3
		self.minion_range = 3
		  
		self.upgrades['swarm'] = (1, 5, "Swarming", "If the target dies to Improvise, gain your imp swarm buff for 2 turns, or extend it by 2 turns.")
		self.upgrades['nightmare'] = (1, 3, "Nightmare", "Improvise also summons one void imp, or one rot imp, at the target location", [Tags.Arcane, Tags.Dark] )
		self.upgrades['promote'] = (1, 7, "Demonic Promotion", "Target an imp to transform it into a fiend. Fiends last 7 times longer than imps. Consumes 7 more charges.")

	def summon_imps(self, x, y):
		imps = [FireImp(), SparkImp(), IronImp()]
		imp = random.choice(imps)
		imp.max_hp = self.get_stat('minion_health')
		imp.spells[0].damage = self.get_stat('damage')
		apply_minion_bonuses(self,imp)
		self.summon(imp, target=Point(x, y), sort_dist=True)
		
	def summon_imps_nightmare(self,x,y):
		imps = [VoidImp(), RotImp()]
		imp = random.choice(imps)
		imp.max_hp = self.get_stat('minion_health')
		imp.spells[0].damage = self.get_stat('damage')
		apply_minion_bonuses(self,imp)
		self.summon(imp, target=Point(x, y), sort_dist=True)

	def cast(self, x, y):
		point = Point(x,y)
		damage_types = [Tags.Physical,Tags.Fire,Tags.Lightning]
		d_type = random.choice(damage_types)
		u = self.caster.level.get_unit_at(x, y)
		self.caster.level.deal_damage(x, y, self.get_stat('damage'), d_type, self)
		if u != None:
			if self.get_stat('promote') and self.cur_charges >= 7 and u.name[-4:] == " Imp": ##This only works if the unit is named 'foo Imp', should avoid imp gates at least.
				self.cur_charges -= 7
				u.kill()
				unit = random.choice([IronFiend(),RedFiend(),YellowFiend()])
				apply_minion_bonuses(self, unit)
				unit.turns_to_death = self.get_stat('minion_duration') * 7
				self.summon(unit=unit,target=point,team=self.caster.team)
			if self.get_stat('swarm') and not u.is_alive():
				buff = self.caster.get_buff(ImpCallBuff)
				if buff == None:
					spell = self.caster.get_or_make_spell(ImpGateSpell)
					self.caster.apply_buff(ImpCallBuff(spell), 2)
				else:
					buff.turns_left += 2
		self.summon_imps(x,y)
		if self.get_stat('nightmare'):
			self.summon_imps_nightmare(x,y)
		yield
		
	def get_description(self):
		desc = "Deals [{damage}_fire:fire] damage, [{damage}_lightning:lightning] damage,"
		desc += " or [{damage}_physical:physical] damage to the target. Then summon a random fire, spark, or iron imp."
		return desc.format(**self.fmt_dict())

	def get_extra_examine_tooltips(self):
		imps = [FireImp(), SparkImp(), IronImp(), VoidImp(), RotImp()]
		for i in imps:
			i.max_hp = 7
			i.spells[0].damage = 7
		imps.insert(3,self.spell_upgrades[0])
		imps.insert(4,self.spell_upgrades[1])
		imps.append(self.spell_upgrades[2])
		return imps

class MetalShardEcho(Buff):
	def on_init(self):
		self.buff_type = BUFF_TYPE_BLESS
		self.stack_type	= STACK_NONE
		self.name = "Echoing Bounce"
		self.color = Tags.Metallic.color
		self.description = "Your next level 2 or higher Metallic or Ice spell casts metal shard at the target location."
		self.owner_triggers[EventOnSpellCast] = self.on_cast

	def on_cast(self, evt):
		if evt.spell.level > 1:
			self.owner.level.queue_spell(self.copy_spell(Point(evt.x, evt.y)))
			
	def copy_spell(self, point):
		spell = self.owner.get_or_make_spell(MetalShard)
		spell.echocast = True
		unit = self.owner.level.get_unit_at(point.x, point.y)
		if not unit:
			return
		if are_hostile(self.owner, unit):
			self.owner.level.act_cast(self.owner, spell, point.x, point.y, pay_costs=False)
		else:
			units = self.owner.level.get_units_in_ball(point, spell.get_stat('range'))
			hostiles = [u for u in units if are_hostile(self.owner, u)]
			if hostiles == []:
				return
			target = random.choice(hostiles)
			self.owner.level.act_cast(self.owner, spell, target.x, target.y, pay_costs=False)
		self.owner.remove_buffs(MetalShardEcho)
		yield

class MetalShard(Spell):
	def on_init(self):
		self.name = "Metal Shard"
		self.asset = ["TcrsCustomModpack", "Icons", "metal_shard"]
		self.tags = [Tags.Metallic, Tags.Sorcery]
		self.level = 1
		self.max_charges = 18
		
		self.damage = 7
		self.damage_type = [Tags.Physical]
		self.range = 10
		self.num_targets = 3
		
		self.echocast = False

		#Kinetic Cascade - Credit Mikhailo Kobiletski
		self.upgrades['echo'] = (1, 2, "Echoing Bounce", "When you cast metal shard, your next level 2 or higher spell also casts metal shard at the target.\nIf there is an ally in the tile, instead cast metal shard at a random enemy in range.")
		self.upgrades['bouncer'] = (1, 4, "Anti-Inelastic Slime", "Each time it ricochets it gains 100% damage.\n"
																"If the wizard cast the spell, at the last unit hit, summon a green slime with the max hp of the total damage dealt, for 10 turns.", [Tags.Slime])
		self.upgrades['UBW'] = (1, 4, "Unlimited Bounce Works", "Consume all charges to gain 1 bounce, and 1 bounce range per charge consumed.\nDeals 2 [fire] damage to each target for each charge consumed", [Tags.Fire])
		#Name came before the upgrade, not a good sign

	def cast(self, x, y):
		#if self.caster.name == "Wizard":
		#	self.caster.xp = self.caster.xp + 3 ##Free xp for testing, comment out for real game.
		bolts = [(self.caster, Point(x, y))]
		ubw_bonus = 0
		if self.get_stat('UBW') and self.cur_charges > 1:
			ubw_bonus = self.cur_charges * 2
			self.cur_charges = 0
		if self.get_stat('echo'):
			if not self.echocast:
				self.caster.apply_buff(MetalShardEcho())
			else:
				self.echocast = False

		target_count = self.get_stat('num_targets') + ubw_bonus
		bounce_range = math.ceil(self.get_stat('range')) / 2 + ubw_bonus
		damage = self.get_stat('damage')
		sum_dmg = 0
		
		prev_target = Point(x, y)
		targets = [self.caster.level.get_unit_at(x, y)]
		for _ in range(target_count): ##Modified version of the updated magic missile ricochet
			candidates = [u for u in self.owner.level.get_units_in_los(prev_target)
						  if are_hostile(self.caster, u)
						  and distance(u, prev_target) < bounce_range
						  and u not in targets]
			if not candidates:
				break

			next_target_unit = min(candidates, key=lambda u: distance(prev_target, u))
			targets.append(next_target_unit)
			next_target = Point(next_target_unit.x, next_target_unit.y)
			bolts.append((prev_target, next_target))
			prev_target = next_target

		bouncer = 0
		for origin, target in bolts:
			#self.caster.level.projectile_effect(origin.x, origin.y, proj_name='physical_ball', proj_origin=origin, proj_dest=target)
			self.caster.level.show_beam(origin, target, Tags.Physical)
			sum_dmg += self.caster.level.deal_damage(target.x, target.y, damage + bouncer, Tags.Physical, self)
			if self.get_stat('UBW') and ubw_bonus > 0:
				sum_dmg += self.caster.level.deal_damage(target.x, target.y, ubw_bonus*2, Tags.Fire, self)
			if self.get_stat('bouncer'):
				bouncer += int(self.get_stat('damage'))
		if self.get_stat('bouncer') and sum_dmg > 0 and self.caster.is_player_controlled:
			unit = GreenSlime()
			unit.max_hp = sum_dmg
			unit.turns_to_death = 10
			apply_minion_bonuses(self, unit)
			self.summon(unit, prev_target)
			yield

	def get_description(self):
		return "Launch a bouncing projecting dealing [{damage}_physical:physical] damage to [{num_targets}:num_targets] targets. Bounce range is half of base range.".format(**self.fmt_dict())

class CauldronBuff(Buff):
	def __init__(self, spell):
		self.spell = spell
		Buff.__init__(self)

	def on_init(self):
		self.global_triggers[EventOnDamaged] = self.on_damage
		self.counter = 0
		self.counter_max = 20
		self.name = "Conjuring Cauldron"
		self.description = ("When %d damage is done by allied minions, summon a toad." % self.counter_max)

	def on_damage(self, evt):
		if not evt.source:
			return
		if evt.source.owner == self.spell.owner:
			return
		if are_hostile(self.spell.owner, evt.source.owner):
			return

		is_tagged_summon = False
		if evt.source.owner:
			if evt.source.owner.source:
				is_tagged_summon = True
		if is_tagged_summon:
			self.counter += evt.damage
			while self.counter > self.counter_max:
				unit = self.spell.get_units()
				apply_minion_bonuses(self.spell, unit)
				self.summon(unit)
				self.counter -= self.counter_max
				self.counter_max += 20

	def on_advance(self):
		if self.counter_max > 5:
			self.counter_max -= 5
		self.description = ("When %d damage is done by allied minions, summon a toad." % self.counter_max)


def GiantToadGhost():
	unit = Unit()
	unit.name = 'Ghoulish Ghosttoad'
	unit.asset = ["TcrsCustomModpack", "Units", "ghost_toad_giant"]
	unit.max_hp = 85
	unit.buffs.append(TrollRegenBuff())
	tongue_attack = PullAttack(damage=3, range=8, color=Tags.Tongue.color)
	tongue_attack.name = "Tongue Lash"
	unit.spells.append(ToadHop())
	unit.spells.append(SimpleMeleeAttack(damage=15, trample=True))
	unit.spells.append(tongue_attack)
	unit.tags = [Tags.Undead, Tags.Nature]
	return unit

def Cauldron():
	unit = Idol()
	unit.tags.append(Tags.Metallic)
	unit.name = "Conjuring Cauldron"
	unit.asset = ["TcrsCustomModpack", "Units", "cauldron"]
	return unit
	
class SummonCauldron(Spell):
	def on_init(self):
		self.name = "Conjuring Cauldron"
		self.tags = [Tags.Nature, Tags.Conjuration]
		self.asset = ["TcrsCustomModpack", "Icons", "cauldron_icon"]
		self.level = 5 ##Level 5,6, 7, 8?? Strong effect and it lasts forever. Inspired by and comparable to Furnace of Sorcery, but its minions reinforce it more.
		
		self.max_charges = 1
		self.range = 4
		self.minion_health = 50
		self.minion_damage = 8
		
		self.must_target_empty = True
		self.must_target_walkable = True

		self.upgrades['king'] = (1, 5, "Kingly Cauldron", "Adds King Toads that summon toad gates. Upgrades regular toads to towering toadbeasts.")
		self.upgrades['firevoid'] = (1, 6, "Potent Pot", "Adds gigantic variations of the fire and void toads. The cauldron gains 100 fire and arcane resistance.", [Tags.Fire, Tags.Arcane])
		self.upgrades['ghost'] = (1, 3, "Spooky Saucepan", "Add a towering variant of the ghost toad. The cauldron gains a dark damage aura for 2 damage in a 7 tile radius.", [Tags.Dark])

	def cast_instant(self,x,y):
		unit = Cauldron()
		if self.get_stat('firevoid'):
			unit.resists[Tags.Fire] = 100
			unit.resists[Tags.Arcane] = 100
		if self.get_stat('ghost'):
			aura = DamageAuraBuff(damage=2, damage_type=[Tags.Dark], radius=7)
			unit.buffs.append(aura)
		unit.apply_buff(CauldronBuff(self))
		self.summon(unit,target=Point(x,y))

	def get_units(self):
		choices = [HornedToad, FlameToad, VoidToad, GhostToad]
		if self.get_stat('king'):
			choices[0] = HornedToadKing
			choices.append(GiantToad)
		if self.get_stat('firevoid'):
			choices.append(FlameToadGiant)
			choices.append(VoidToadGiant)
		if self.get_stat('ghost'):
			choices.append(GiantToadGhost)
		return random.choice(choices)()

	def get_description(self):
		return ("Summon a Cauldron at target tile. For every 20 damage dealt by a minion, summon a toad, which can be any variant of: regular, flame, void, or ghost.\n"
				"The damage needed to summon the next toad increases by 20 each time a toad is summoned. Each turn it decreases by 5.").format(**self.fmt_dict())
	
	def get_extra_examine_tooltips(self):
		return [HornedToad(), FlameToad(), VoidToad(), GhostToad(), self.spell_upgrades[0], HornedToadKing(), GiantToad(),
		self.spell_upgrades[1], FlameToadGiant(), VoidToadGiant(), self.spell_upgrades[2], GiantToadGhost()]

class CorpseExplosionBuff(Buff):
	def __init__(self, spell):
		self.spell = spell
		Buff.__init__(self)

	def on_init(self):
		self.buff_type = BUFF_TYPE_CURSE
		self.name = "Corpse Explosion"
		self.color = Tags.Blood.color
		self.asset = ["TcrsCustomModpack", "Misc", "corpse_explosion_buff"]
		self.stack_type = STACK_DURATION
		self.owner_triggers[EventOnDeath] = self.on_death
		if self.spell.get_stat('remove_resistance'):
			self.resists[Tags.Fire] = -25
			self.resists[Tags.Physical] = -25
			self.resists[Tags.Lightning] = -25
			
	def on_advance(self):
		damage = self.spell.get_stat('damage')
		if self.spell.get_stat('giant'):
			damage += math.floor(self.owner.max_hp / 10)
		self.owner.deal_damage(damage, Tags.Physical, self.spell)
		
	def on_death(self, evt):
		self.owner.level.queue_spell(self.burst())

	def burst(self):
		point = Point(self.owner.x,self.owner.y)
		if self.spell.get_stat('giant'):
			bonus_rad = math.floor(self.owner.max_hp / 10)
		else:
			bonus_rad = 0
		for unit in self.owner.level.get_units_in_ball(self.owner, self.spell.get_stat('radius') + bonus_rad):
			if are_hostile(self.spell.owner, unit):
				for p in self.owner.level.get_points_in_line(self.owner, unit)[1:-1]:
					self.owner.level.show_effect(p.x, p.y, Tags.Blood, minor=True)
				
				damage = unit.deal_damage(self.spell.get_stat('damage'), Tags.Fire, self.spell)
				if unit.is_alive():
					unit.apply_buff(CorpseExplosionBuff(self.spell), 1)
		if self.spell.get_stat('bloody'):
			bs = self.spell.owner.get_or_make_spell(Bloodshift)
			self.spell.owner.level.act_cast(self.spell.owner, bs, point.x, point.y, pay_costs=False)
		yield


class CorpseExplosion(Spell):
	def on_init(self):
		self.name = "Corpse Explosion"
		self.asset = ["TcrsCustomModpack", "Icons", "corpse_explosion"]
		self.level = 3 ##Tentative level 3, perhaps higher. 3s can be autocast by some of my spells, comparable immediately to deathchill
		self.tags = [Tags.Enchantment, Tags.Fire, Tags.Blood]

		self.hp_cost = 12
		self.max_charges = 10
		self.damage = 8
		self.damage_type = [Tags.Physical, Tags.Fire]
		self.range = 8
		self.radius = 4
		
		self.can_target_empty = False
		
		self.upgrades['remove_resistance'] = (1, 3, "Chaos Curse", "Target loses 25 [physical], [fire], and [lightning] resistance.", [Tags.Chaos])
		self.upgrades['bloody'] = (1, 4, "Blood Explosion", "The explosion also casts your blood shift spell.")
		self.upgrades['giant'] = (1, 3, "Giant Killer", "Deal bonus damage each turn equal to 10% of target's max hp, and the explosion radius increases by 1 for every 10 max hp the target has.")

	def get_impacted_tiles(self, x, y):
		point = [Point(x, y)]
		return point
		
	def cast(self, x, y):
		target = self.caster.level.get_unit_at(x, y)
		if not target:
			return
		target.apply_buff(CorpseExplosionBuff(self))
		yield
		
	def get_description(self):
		return ("Deal [{damage}_physical:physical] damage to the target each turn until it dies.\n"
				"If the target dies, it explodes dealing [{damage}_fire:fire] damage to all enemies within a [{radius}_tiles:radius] radius "
				"and applies the debuff for 1 turn.\n").format(**self.fmt_dict())
	
class AccumulatorBuff(Buff):
	def __init__(self, spell):
		self.spell = spell
		Buff.__init__(self)

	def on_init(self):
		self.buff_type = BUFF_TYPE_BLESS
		self.name = "Accumulator"
		self.color = Tags.Metallic.color
		self.stack_type = STACK_REPLACE

class Accumulator(Upgrade):
	def on_init(self):
		self.level = 2
		self.name = "Accumulator"
		self.description = ("Whenever you cast a metallic spell, the number of Bags of Bugs your next summons flywheel is increased by the level of the metallic spell.\n"
							"All minions summoned by the spell become metallic.\n"
							"Adds the [Metallic] tag").format(**self.fmt_dict())
		self.owner_triggers[EventOnSpellCast] = self.on_cast
		self.tags = [Tags.Metallic]

	def on_cast(self, evt):
		if Tags.Metallic not in evt.spell.tags:
			return
		if evt.spell.name == "Flywheel":
			return
		buff = AccumulatorBuff(self)
		buff.level = evt.spell.level
		buff.description = "Summon " + str(buff.level) + " extra bags of bugs, and turn them metallic"
		self.owner.apply_buff(buff)

	def on_applied(self, owner):
		self.spell_tag_update(FlyWheel, Tags.Metallic)

	def on_unapplied(self):
		self.spell_tag_update(FlyWheel, Tags.Metallic, add=False)

class FlyWheel(Spell):

	def on_init(self):
		self.name = "Flywheel"
		self.asset = ["TcrsCustomModpack", "Icons", "flywheel"]
		self.level = 2 ##Aiming for level 2, scales well with skills, but starts weak.
		self.tags = [Tags.Nature, Tags.Conjuration]
		
		self.max_charges = 5
		self.range = 0
		self.radius = 3
		self.minion_health = 16
		self.minion_damage = 4
		self.minion_duration = 5
		self.num_summons = 2
		
		self.add_upgrade(Accumulator())
		self.upgrades['arcane'] = (1, 2, "Arcanization", "Summons brain bugs and brain flies, and melts walls in the ring.", [Tags.Arcane])
		self.upgrades['bigbag'] = (1, 4, "Giant Bag", "Replace the bags of bugs with giant bags of bugs.")

	def make_unit(self):
		if self.get_stat('arcane'):
			unit = BagOfBugsBrain()
		elif self.get_stat('bigbag'):
			unit = BagOfBugsGiant()
			unit.buffs[0].description = "On death, spawn 32 Fly Clouds"
		else:
			unit = BagOfBugs()
		apply_minion_bonuses(self, unit)
		unit.turns_to_death = None
		if self.owner.has_buff(Accumulator):
			BossSpawns.apply_modifier(BossSpawns.Metallic, unit)
		return unit

	def make_unit_flies(self):
		if self.get_stat('arcane'):
			unit = BrainFlies()
		else:
			unit = FlyCloud()
		unit.max_hp = self.get_stat('minion_health') // 4
		unit.damage = self.get_stat('minion_damage') // 4
		apply_minion_bonuses(self, unit)
		if self.owner.has_buff(Accumulator):
			BossSpawns.apply_modifier(BossSpawns.Metallic, unit)
		return unit

	def cast_instant(self, x, y):
		bonus_summons = 0
		if self.caster.has_buff(AccumulatorBuff):
			bonus_summons = self.caster.get_buff(AccumulatorBuff).level
			self.caster.remove_buffs(AccumulatorBuff)
		flybags = self.get_stat('num_summons') + bonus_summons
		points = self.get_impacted_tiles(x,y)
		random.shuffle(points)
		for point in points:
			if self.get_stat('arcane'):
				if self.caster.level.tiles[point.x][point.y].is_wall():
					self.caster.level.make_floor(point.x, point.y)
					
			unit = self.caster.level.tiles[point.x][point.y].unit
			if unit != None:
				continue

			if self.caster.level.tiles[point.x][point.y].is_floor() and flybags > 0:
				flybags -= 1
				bag = self.make_unit()
				self.summon(bag, point) 
			else:
				if self.caster.level.tiles[point.x][point.y].is_wall():
					continue
				fly = self.make_unit_flies()
				self.summon(fly, point)

				
	def get_impacted_tiles(self, x, y):
		points = self.caster.level.get_points_in_ball(self.caster.x, self.caster.y, self.get_stat('radius'))
		points = [p for p in points if p != Point(self.caster.x, self.caster.y) and distance(self.caster, p) >= self.radius - 1]
		return points

	def get_extra_examine_tooltips(self):
		giantbagfix = BagOfBugsGiant()
		giantbagfix.buffs[0].description = "On death, spawn 32 Fly Clouds"
		return [BagOfBugs(), FlyCloud(), self.spell_upgrades[0], BagOfBugsBrain(), BrainFlies(), self.spell_upgrades[1], giantbagfix, self.spell_upgrades[2]]

	def get_description(self):
		return ("Summon [{num_summons}:num_summons] Bags of Bugs in random tiles in a ring around the caster. "
				"The Bags have [{minion_health}_HP:minion_health] and have a melee attack dealing [{minion_damage}_physical:physical] damage.\n"
				"Every other tile in the ring is filled with Fly Swarms that last for [{minion_duration}_turns:minion_duration]. "
				"Fly Swarms have 1/4th as much health and damage as the Bags of Bugs.").format(**self.fmt_dict())

class Rockfall(Spell):
	def on_init(self):
		self.name = "Rockfall"
		self.asset = ["TcrsCustomModpack", "Icons", "rockfall"]
		self.tags = [Tags.Nature, Tags.Sorcery]
		self.level = 4 ## Probably a level 4 or 5 spell? It should be low-ish impact with many charges
		
		self.max_charges = 15
		self.damage = 30
		self.damage_type = [Tags.Physical]
		self.range = 7
		self.radius = 1
		
		self.mod_radius = 3
		self.cast_on_walls = True

		#self.upgrades['rolling'] = (1, 0, "Rolling Stone", "Deal damage in a wide line towards the target instead of just at the area.")
		self.upgrades['radius'] = (2, 3, "Radius")
		self.upgrades['earthquake'] =  (1, 5, 'Quaker', 'Cast earthquake at your location after this spell.')
		self.upgrades['walleater'] = (1, 3, 'Walleater', 'If the center tile is a wall, cast earth sentinel at that point.')
		self.upgrades['chaos'] = (1, 5, 'Chaotic Rock', 'Also deal fire or lightning damage to each tile.', [Tags.Chaos])
		##TODO Absorb a nearby wall to empower radius by 1?
	def cast(self, x, y):
		half_radius = math.ceil(self.get_stat('radius') / 2)
		for p in self.caster.level.get_points_in_rect(x - half_radius, y - half_radius, x + half_radius, y + half_radius):
			self.caster.level.deal_damage(p.x, p.y, self.get_stat('damage'), Tags.Physical, self)
			if self.get_stat('chaos'):
				if random.random() > 0.5:
					self.caster.level.deal_damage(p.x, p.y, self.get_stat('damage'), Tags.Fire, self)
				else:
					self.caster.level.deal_damage(p.x, p.y, self.get_stat('damage'), Tags.Lightning, self)

			cur_tile = self.caster.level.tiles[p.x][p.y]
			if cur_tile.is_chasm:
				self.caster.level.make_floor(p.x, p.y)
		cur_tile = self.caster.level.tiles[x][y]
		if self.get_stat('earthquake'):
			quake = self.caster.get_or_make_spell(Spells.EarthquakeSpell)
			for _ in self.caster.level.act_cast(self.caster, quake, self.caster.x, self.caster.y, pay_costs=False, queue=False):
				pass
		if cur_tile.is_wall() and self.get_stat('walleater'):
			sentinel = self.caster.get_or_make_spell(Spells.SummonEarthElemental)
			self.caster.level.make_floor(x, y)
			for _ in self.caster.level.act_cast(self.caster, sentinel, x, y, pay_costs=False, queue=False):
				pass
		yield

	def get_description(self):
		mod_radius = self.get_stat('radius')
		mod_radius = 1 + math.ceil(mod_radius / 2) * 2
		return ("Drop a rock at target location, dealing [{damage}_physical:physical] damage in a " + str(mod_radius) + "x" + str(mod_radius) + " square\n"
				"The area increases by 1 tile in all directions for every 2 points of radius.\n"
				"Fills in chasms in the area of effect.").format(**self.fmt_dict())

	def get_impacted_tiles(self, x, y):
		half_radius = math.ceil(self.get_stat('radius') / 2)
		return self.caster.level.get_points_in_rect(x - half_radius, y - half_radius, x + half_radius, y + half_radius)

	
class IcebeamDebuff(Buff):
	def __init__(self, spell):
		Buff.__init__(self)
		self.spell = spell

	def on_init(self):
		self.buff_type = BUFF_TYPE_CURSE
		self.name = "Frigid Cold"
		self.description = "Casting Freezing Beam again will freeze you. Cast any fire spell to remove this debuff immediately."
		self.color = Tags.Ice.color
		self.owner_triggers[EventOnSpellCast] = self.on_cast
		
	def on_cast(self, spell_cast_event):
		if Tags.Fire in spell_cast_event.spell.tags: #and spell_cast_event.spell.name != "Ice Beam": ##Can be added back.
			self.owner.remove_buff(self)

class Icebeam(Spell):
	def on_init(self):
		self.name = "Freezing Beam"
		self.asset = ["TcrsCustomModpack", "Icons", "icebeam"]
		self.tags = [Tags.Ice, Tags.Sorcery]
		self.level = 4 #Tentative level 5 spell, maybe 4? Pillar of fire and void beam are good comparisons
		
		self.max_charges = 6
		self.range = 6
		#self.melee = True ##Revert if I can figure out this stupid spell. 
		self.damage = 45
		self.damage_type = [Tags.Ice]

		self.total_damage = 0
		self.cast_on_walls = True

		self.upgrades['knight'] = (1, 4, "Storm Beam", "Each 180 damage dealt by the beam summons a storm knight.", [Tags.Conjuration])
		self.upgrades['icemaw'] = (1, 4, "Icy Maw", "Cast your hungry maw on tiles where an enemy died to this spell.", [Tags.Arcane])
		self.upgrades['chasm'] = (1, 3, "Faery", "Summons winter faeries over each chasm. They last 11 turns.", [Tags.Conjuration])
		##self.upgrades['backwards'] = (1, 3, "Backblast", "Deal fire damage in a cone behind you after casting.")
			
	def get_description(self):
		return ("Deals [{damage}_ice:ice] damage in a straight beam. The beam pierces walls and continues until the end of the level.\n"
			   "Debuff yourself for 3 turns or until you cast a [fire] spell. If you cast this spell with the debuff, freeze yourself for 3 turns.").format(**self.fmt_dict())

	def get_extra_examine_tooltips(self): 
		return [self.spell_upgrades[0], StormKnight(), self.spell_upgrades[1], self.spell_upgrades[2], FairyIce()]

	def get_impacted_tiles(self, x, y):
		size = self.caster.level.width
		size_y = self.caster.level.height
		start = Point(self.caster.x, self.caster.y)
		run = self.caster.x - x
		rise = self.caster.y - y
		if run == 0 and rise == 0:
			return
		finalx = x
		finaly = y
		while finalx >= 0 and finalx <= size and finaly >= 0 and finaly <= size:
			finalx -= run
			finaly -= rise
		target = Point(finalx, finaly)
		
		first_pass = Bolt(self.caster.level, start, target, find_clear=False, two_pass=False)
		second_pass = []
		for p in first_pass:
			if self.caster.level.is_point_in_bounds(p):
				second_pass.append(p)

		return second_pass

	def cast(self,x,y):
		if self.caster.has_buff(IcebeamDebuff):
			self.caster.apply_buff(FrozenBuff(),4)
		else:
			self.caster.apply_buff(IcebeamDebuff(self),4)
		points = self.get_impacted_tiles(x,y)

		cur_damage = 0
		for point in points:
			#print(point)
			#if self.owner.level.tiles[point.x][point.y].is_wall():
			#	self.owner.level.make_floor(point.x, point.y)
			if not self.caster.level.is_point_in_bounds(point):
				continue
			if self.get_stat('chasm') and self.caster.level.tiles[point.x][point.y].is_chasm:
				self.summon(self.make_winter_fae(),point)
			unit = self.caster.level.get_unit_at(*point)
			cur_damage += self.caster.level.deal_damage(point.x, point.y, self.get_stat('damage'), Tags.Ice, self)
			if unit and not unit.is_alive() and self.get_stat('icemaw'):
				summon = self.caster.get_or_make_spell(Spells.VoidMaw)
				for _ in self.caster.level.act_cast(self.caster, summon, unit.x, unit.y, pay_costs=False, queue=False):
					pass
		if self.get_stat('knight'):
			self.total_damage += cur_damage
			while self.total_damage >= 180:
				knight = StormKnight()
				apply_minion_bonuses(self, knight)
				self.summon(knight, self.caster)
				self.total_damage -= 180
		yield

	def make_winter_fae(self):
		fae = FairyIce()
		apply_minion_bonuses(self, fae)
		fae.turns_to_death = 11
		return fae


class AbsorbBuff(Buff):
	def __init__(self, spell):
		self.spell = spell
		Buff.__init__(self)

	def on_init(self):
		self.name = "Absorption"
		self.buff_type = BUFF_TYPE_BLESS
		self.color = Tags.Blood.color
		self.stack_type = STACK_REPLACE
		self.resists = {}

class BarrierBuff(Buff):
	def __init__(self, res_vals):
		Buff.__init__(self)
		self.name = "Barrier"
		self.buff_type = BUFF_TYPE_BLESS
		self.color = Tags.Blood.color
		self.stack_type = STACK_REPLACE
		self.restags = res_vals
		for res in self.restags:
			self.resists[res[0]] = res[1]

class Absorb(Spell):

	def on_init(self):
		self.name = "Absorb"
		self.tags = [Tags.Arcane, Tags.Enchantment, Tags.Sorcery]
		self.asset = ["TcrsCustomModpack", "Icons", "absorb"]
		self.level = 2 ##Level 2-3 perhaps? Immediate comparisons are touch of death and mystic power
		
		self.max_charges = 5
		self.range = 1
		self.melee = True
		self.damage = 50
		self.damage_type = [Tags.Arcane]
		self.duration = 10
		
		self.bonus = 15
		self.can_target_empty = False

		self.upgrades['minions'] = (1, 3, "Shadow Siphon", "Deals [dark] damage as well. Applies damage bonus to minion damage as well.", [Tags.Dark])
		self.upgrades['stealresist'] = (1, 4, "Hypermorphic Armor", "Deals [poison] damage as well. Copy the target's resistances as well.", [Tags.Slime])
		self.upgrades['leech'] = (1, 3, "Leech", "Deals [physical] damage as well. Heals you for the damage dealt.", [Tags.Blood])

	def get_description(self):
		return ("Deal [{damage}_arcane:arcane] damage to one unit in melee range, then gain 15 bonus damage to spells based on the target's tags.\n"
				"Convert all damage tags e.g. [Fire] enemies to [Fire] spell damage, and also converts [Living] to [Nature], [Undead] to [Dark] damage.\n"
				"Lasts [{duration}_turns:duration].").format(**self.fmt_dict())

	def cast_instant(self, x, y):
		unit = self.caster.level.get_unit_at(x, y)
		buff = AbsorbBuff(self)
		tagconv = TagConvertor()
		for t in unit.tags:
			if t in tagconv:
				match_tag = tagconv[t]
			else:
				match_tag = t
			buff.tag_bonuses[match_tag]['damage'] = self.bonus
			if self.get_stat('minionbonus'):
				buff.tag_bonuses[match_tag]['minion_damage'] = self.bonus
				
		if self.get_stat('stealresist'):
			res_vals = []
			for tag in unit.resists.keys():
				if tag != Tags.Heal:
					resval = unit.resists[tag]
					res_vals.append([tag,resval])
			defense_buff = BarrierBuff(res_vals)
			self.caster.apply_buff(defense_buff, self.get_stat('duration'))

		dtypes = self.damage_type
		if self.get_stat('minions'):
			dtypes.append(Tags.Dark)
		if self.get_stat('stealresist'):
			dtypes.append(Tags.Poison)
		if self.get_stat('leech'):
			dtypes.append(Tags.Physical)
		damage = self.get_stat('damage')
		total_dmg = 0
		for dtype in self.damage_type:
			total_dmg += unit.deal_damage(damage, dtype, self)
		self.caster.apply_buff(buff, self.get_stat('duration'))
		if self.get_stat('leech'):
			self.caster.deal_damage(-total_dmg, Tags.Heal, self)



class HasteUpgrade(Upgrade):
	def on_init(self):
		self.level = 5
		self.name = "Lightning Speed"
		self.description = "Whenever you cast a [lightning] spell other than haste, grant haste to one ally for 3 turns."
		self.owner_triggers[EventOnSpellCast] = self.on_cast

	def on_cast(self, evt):
		if Tags.Lightning not in evt.spell.tags:
			return
		if isinstance(evt.spell, Haste):
			return 

		eligible_units = [u for u in self.owner.level.units if not are_hostile(u, self.owner) and not u.is_player_controlled]
		if eligible_units == []:
			return
		unit = random.choice(eligible_units)
		unit.apply_buff(HasteBuff(),3)

class Haste(Spell):
	def on_init(self):
		self.name = "Haste"
		self.asset = ["TcrsCustomModpack", "Icons", "haste_icon"]
		self.level = 2 #Hard to judge its efficiency, this spell scales with your minions.
		self.tags = [Tags.Lightning, Tags.Enchantment]
		
		self.max_charges = 15
		self.range = 99
		self.num_targets = 2
		
		self.max_channel = 15
		self.requires_los = False
		self.can_target_empty = False
		self.can_target_self = False
		
		self.upgrades['quick'] = (1, 5, "Quickening", "Hasted allies gain the quickened modifier, if unmodified.")
		self.add_upgrade(HasteUpgrade())
		self.upgrades['enduring'] = (1, 1, "Endurance", "No longer channeled, instead lasts for [10:duration] turns. Does not follow location of target unit.")

	def get_description(self):
		return ("Target unit, and up to [{num_targets}:num_targets] allies in a 4 tile radius, take an extra turn after acting.\n"
				"This spell can be channeled for up to [{max_channel}_turns:duration]\n"
				"The spell follows location of the targeted unit while channeled, or target point if the unit has died.").format(**self.fmt_dict())

	def can_cast(self, x, y):
		unit = self.caster.level.get_unit_at(x, y)
		return unit and unit != self.caster and not unit.is_player_controlled
	
	def get_impacted_tiles(self, x, y):
		targets = []
		#group = self.caster.level.get_connected_group_from_point(x, y, num_targets=self.get_stat('num_targets'))
		for target in self.caster.level.get_units_in_ball(Point(x,y), 4):
		#for target in self.caster.level.get_units_in_los(self.caster): #Replace with group for connected version
			if not self.caster.level.are_hostile(self.caster, target) and target != self.caster:
				targets.append(target)
		return targets
	
	def cast(self, x, y, channel_cast=False):
		targets = self.get_impacted_tiles(x,y)
		if targets == []:
			return
		target = self.caster.level.get_unit_at(x,y)
		if target not in targets and target != None: 
			targets[0] = target
		if target == None or target.is_alive() == False:
			target = Point(x,y)

		if not channel_cast and not self.get_stat('enduring'):
			self.caster.apply_buff(ChannelBuff(self.cast, target=target), self.get_stat('max_channel'))
			return

		self.caster.level.show_path_effect(self.caster, target, Tags.Lightning, minor=True)
		count = self.get_stat('num_targets')
		for u in targets:
			if count > 0:
				if u.is_alive():
					count -= 1
					buff = HasteBuff()
					if self.get_stat('quick'):
						apply_modifier(BossSpawns.Quickened,u)
					duration = 2
					if self.get_stat('enduring'):
						duration = 10
					u.apply_buff(buff,duration)
			else:
				break
		yield

class EnchantingCross(Spell):
	def on_init(self):
		self.name = "Enchanting Cross"
		self.asset = ["TcrsCustomModpack", "Icons", "enchanting_cross"]
		self.tags = [Tags.Arcane, Tags.Enchantment]
		self.level = 4 ##Immediately comparable to cantrip cascade, but worse. Level 4? It's actually pretty reasonable. Level 5?
		
		self.max_charges = 3
		self.range = 0
		self.radius = 8
		
		self.requires_los = False
		
		self.upgrades['higher'] = (1, 1, "Higher Power", "Adds your Corpse Explosion and Death Chill spells into the pool of random spells it chooses from.")
		self.upgrades['selfbuff'] = (1, 4, "Selfish", "Casts one of your self targeted enchantments randomly for free.")
		self.upgrades['doublecross'] = (1, 3, "Double Cross", "Adds a diagonal cross.")

	def get_description(self):
		return ("Cast one of your level 1 or 2 [enchantment] spells on each enemy in a [{radius}_tile:radius] cross for free.\n"
				"The enchantment spells must have a range greater than 1.").format(**self.fmt_dict())

	def get_impacted_tiles(self, x, y):
		rad = self.get_stat('radius')
		for i in range(-rad, rad + 1):
			yield Point(x+i, y)
			if i != 0:
				yield Point(x, y+i)
		if self.get_stat('doublecross'):
			rad = self.get_stat('radius')
			for i in range(-rad, rad + 1):
				yield Point(x+i, y-i)
				yield Point(x-i, y-i)
				if i != 0:
					yield Point(x-i, y+i)
					yield Point(x+i, y+i)

	def cast_instant(self, x, y): ##Exclude level 3 spells that buff allies? Suspend mortality and my own steel fangs / icy path. Icy path will definitely cause problems.
		targ_spells = []
		self_spells = []
		if self.get_stat('higher'):
			dc = self.caster.get_or_make_spell(DeathChill)
			ce = self.caster.get_or_make_spell(CorpseExplosion)
			targ_spells.append(dc)
			targ_spells.append(ce)
		for s in self.caster.spells:
			if Tags.Enchantment not in s.tags:
				continue
			if s.range == 0:
				self_spells.append(s)
			elif s.level <= 3:
				targ_spells.append(s)
				
		if self.get_stat('selfbuff'):
			if self_spells == []:
				return
			self_spell = random.choice(self_spells)
			self.caster.level.act_cast(self.caster, self_spell, self.caster.x, self.caster.y, pay_costs=False)
			
		units = [self.caster.level.get_unit_at(p.x, p.y) for p in self.get_impacted_tiles(x, y)]
		enemies = set([u for u in units if u and are_hostile(u, self.caster)])
		print(enemies)
		if targ_spells == [] or enemies == set():
			return
		pairs = []
		for e in enemies:
			pairs.append([e, random.choice(targ_spells)])
		random.shuffle(pairs)
		
		for enemy, spell in pairs:
			self.caster.level.act_cast(self.caster, spell, enemy.x, enemy.y, pay_costs=False)

	
class BloodOrbBuff(Buff):
	def __init__(self, spell):
		self.spell = spell
		Buff.__init__(self)

	def on_init(self):
		self.name = "Blood Orb"
		self.buff_type = BUFF_TYPE_BLESS
		self.color = Tags.Blood.color
		self.stack_type = STACK_NONE
		self.global_triggers[EventOnDamaged] = self.on_damage
		self.owner_triggers[EventOnDeath] = self.on_death
		self.total_damage = 1

	def on_damage(self, evt):
		if evt.source.owner == self.owner and are_hostile(self.owner, evt.unit):
			self.total_damage += evt.damage
		if self.spell.get_stat('deathshock') and self.total_damage > 50:
			units = [u for u in self.owner.level.units if are_hostile(self.owner, u) and not u.is_player_controlled]
			unit = random.choice(units)
			spell = self.spell.owner.get_or_make_spell(DeathShock)
			self.spell.owner.level.act_cast(self.spell.owner, spell, unit.x, unit.y, pay_costs=False, queue=True)
			self.total_damage -= 50

	def on_death(self, evt):
		if self.spell.get_stat('worm'):
			unit = WormBall(self.total_damage)
			self.spell.caster.level.summon(self.owner,unit,Point(self.owner.x,self.owner.y))
			
class BloodOrbSpell(Spells.OrbSpell):

	def on_init(self):
		self.name = "Blood Orb"
		self.tags = [Tags.Blood, Tags.Orb, Tags.Conjuration]
		self.asset = ["TcrsCustomModpack", "Icons", "blood_orb_icon"]
		self.level = 6 ##Level 6 or 7 perhaps? Very strong effect but limited to dark damage.
	
		self.hp_cost = 25
		self.max_charges = 4
		self.range = 9
		self.minion_health = 30
	
		self.upgrades['range'] = (5, 3, "Range", "Gains 5 max range.") ##TODO add a cooler upgrade
		self.upgrades['worm'] = (1, 5, "Lumbricus", "When the orb dies it creates a wormball with max hp equal to the damage the orb dealt to enemies.")
		self.upgrades['deathshock'] = (1, 6, "Bloody Shocking", "You casts your death shock on a random enemy for each 50 damage the orb deals to enemies.",[Tags.Lightning])

	def on_orb_move(self, orb, next_point):
		for _ in self.caster.level.act_cast(orb, orb.spells[0], orb.x, orb.y, pay_costs=False, queue=False):
			pass
		orb.spells[0].radius += 1 ##TODO this was never correct

	def on_make_orb(self, orb):
		orb.name = "Blood Orb"
		orb.asset =  ["TcrsCustomModpack", "Units", "blood_orb"]
		orb.tags.append(Tags.Blood)
		orb.resists[Tags.Physical] = 0
		orb.max_hp = self.minion_health * 5
		orb.cur_hp = self.minion_health
		spell = grant_minion_spell(Spells.DrainPulse, orb, self.caster)
		spell.statholder = orb
		spell.radius = 1
		if self.get_stat('worm') or self.get_stat('deathshock'):
			orb.apply_buff(BloodOrbBuff(self))

	def on_orb_collide(self, orb, next_point):
		orb.level.show_effect(next_point.x, next_point.y, Tags.Physical)
		yield

	def get_description(self):
		return ("Summon a blood orb next to the caster, which casts your drain pulse each turn, "
				"but this drain pulse starts with a radius of 1 and gains 1 each turn. It can hit the Wizard.\n"
				"The orb has no will of its own, each turn it will float one tile towards the target.\n"
				"The orb can be destroyed by [physical] damage.").format(**self.fmt_dict())


class IcepathBuff(Buff):
	def __init__(self, spell, points):
		self.points = points
		self.spell = spell
		Buff.__init__(self)

	def on_init(self):
		self.name = "Ice Path"
		self.buff_type = BUFF_TYPE_BLESS
		self.color = Tags.Ice.color
		self.stack_type = STACK_REPLACE
		self.resists[Tags.Ice] = 100
		self.index = 0
		self.owner_triggers[EventOnMoved] = self.on_move
		
	def on_move(self, evt):
		if evt.teleport:
			self.owner.remove_buff(self)

	
	def on_advance(self):
		if self.index > len(self.points):
			self.owner.remove_buff(self)
			return
		if self.index == 0:
			firstp = Point(self.owner.x,self.owner.y)
		point = self.points[self.index]

		cur_tile = self.owner.level.tiles[point.x][point.y]
		if cur_tile.is_chasm:
			self.owner.level.make_floor(point.x, point.y)
			
		if self.spell.get_stat('storms'):
			targets = [u for u in self.owner.level.get_units_in_los(self.owner) if are_hostile(u, self.owner) and (u.resists[Tags.Lightning] != 100 or u.resists[Tags.Ice] != 100)]
			if targets  != []:
				random.shuffle(targets)
				u = targets[0]
				u.deal_damage(self.spell.get_stat('damage', base=8), Tags.Ice, self)
				u.deal_damage(self.spell.get_stat('damage', base=8), Tags.Lightning, self)

		unit_blocker = self.owner.level.get_unit_at(point.x, point.y)
		if self.spell.get_stat('reaper') and unit_blocker != None:
			death_touch = self.owner.get_or_make_spell(Spells.TouchOfDeath)
			self.owner.level.act_cast(self.owner, death_touch, point.x, point.y, pay_costs=False)

		if self.owner.level.can_move(self.owner, point.x, point.y, teleport=False):
			self.owner.level.show_effect(self.owner.x, self.owner.y, Tags.Ice)
			self.owner.level.act_move(self.owner, point.x, point.y, teleport=False)

			if self.spell.get_stat('thorn'):
				unit = IceThorn()
				apply_minion_bonuses(self, unit)
				if self.index == 0:
					p = firstp
				else:
					p = self.points[self.index-1]
				self.owner.level.summon(self.spell.caster,unit,p)
		else:
			self.points = self.points[:-1]
			self.points.insert(0,point)
		self.index += 1

def IceThorn():
	unit = FaeThorn()
	unit.name = "Icy Thorn"
	unit.stationary = True
	unit.tags.append(Tags.Ice)
	unit.asset_name = "spriggan_bush_icy"
	unit.spells = [SimpleRangedAttack(damage=4, range=3, damage_type=Tags.Ice)]
	return unit

class Icepath(Spell):
	def on_init(self):
		self.name = "Icy Path"
		self.level = 3 ##Level 3 seems reasonable. Maybe 2? It's very efficient against melee units and ice damage and not too amazing against all other things
		self.tags = [Tags.Enchantment, Tags.Ice, Tags.Translocation]
		self.asset = ["TcrsCustomModpack", "Icons", "icepath"]
		
		self.max_charges = 15
		self.range = 10
		
		self.quick_cast = 1
		self.must_target_empty = True
		
		self.upgrades[('storms', 'damage')] = ([1,8], 2, "Cloak of Storms", "Deal [8:damage] [Ice] and [8:damage] [Lightning] damage to 1 unit in line of sight each turn.", [Tags.Lightning])
		self.upgrades['reaper'] = (1, 1, "Reaper's Path", "If there is a unit blocking your path, use your touch of death on it before attempting to move.", [Tags.Dark])
		self.upgrades['thorn'] = (1, 4, "Thornpath", "Summon icy thorns each turn in the tile behind you.", [Tags.Conjuration])

	def get_description(self):
		return ("Target a point to create a path for your wizard to automatically move towards, one tile per turn. Can cross chasms, cannot displace units.\n"
				"Become immune to [ice] during the effect. Target another tile to change your destination.\n"
				"The buff ends if you teleport.").format(**self.fmt_dict())

	def cast(self, x, y):
		points = self.get_impacted_tiles(x,y)
		self.caster.apply_buff(IcepathBuff(self,points),len(points))
		yield

	def get_impacted_tiles(self, x, y):
		start = Point(self.caster.x, self.caster.y)
		target = Point(x, y)
		return list(Bolt(self.caster.level, start, target))

class ScrollBreath(BreathWeapon):
	def on_init(self):
		self.name = "Reading Rainbow"
		self.damage = 8
		self.damage_type = [Tags.Fire, Tags.Ice, Tags.Lightning, Tags.Arcane, Tags.Dark, Tags.Poison, Tags.Holy, Tags.Physical]
		self.cool_down = 6
		self.scrolls = ScrollConvertor()
		self.scrolls[Tags.Metallic] = [MetalShard,LivingMetalScroll]

	def get_description(self):
		return "Breathes a cone of pure linguistics dealing %d damage to occupied tiles and summoning scrolls in empty ones." % self.damage

	def make_scrolls(self,tag):
		if tag == Tags.Poison:
			tag = Tags.Nature
		elif tag == Tags.Physical:
			tag = Tags.Metallic
		unit = self.scrolls.get(tag)[1]()
		cantrip = grant_minion_spell(self.scrolls.get(tag)[0], unit, self.caster, 3)
		unit.apply_buff(LivingScrollSuicide())
		return unit

	def per_square_effect(self, x, y):
		tag = random.choice(self.damage_type)
		scroll = self.make_scrolls(tag)
		scroll.turns_to_death = 2
		unit = self.caster.level.get_unit_at(x, y)
		if unit:
			self.caster.level.deal_damage(x, y, self.damage, tag, self) ##Some sort of error involving this. Maybe it killed a target and tried to summon a scroll also?
		else:
			self.summon(scroll, Point(x, y))
			
def BookWyrm():
	dragon = Unit()
	dragon.name = "Bookwyrm"
	dragon.asset = ["TcrsCustomModpack", "Units", "bookwyrm"]
	dragon.tags = [Tags.Dragon, Tags.Construct, Tags.Sorcery]

	dragon.max_hp = 31
	dragon.shields = 1
	dragon.flying = True
	dragon.spells.append(ScrollBreath())
	dragon.spells.append(SimpleMeleeAttack(8))

	return dragon
		
class SummonBookwyrm(Spell):
	def on_init(self):
		self.name = "Word of Wyrms"
		self.tags = [Tags.Word, Tags.Dragon, Tags.Conjuration]
		self.asset = ["TcrsCustomModpack", "Icons", "word_of_wyrms"]
		self.level = 7
		
		self.max_charges = 1
		self.range = 0
		self.duration = 1
		
		example = BookWyrm()
		self.minion_health = example.max_hp
		self.minion_range = example.spells[0].range
		self.minion_damage = example.spells[1].damage
		
		self.self_target = True

		self.upgrades['double'] = (1, 5, "Double Dragon", "Summons an extra bookwyrm.")
		self.upgrades['duration'] = (1, 2, "Terrifying", "The fear lasts for 1 more turn.", [Tags.Dark])
		self.upgrades['vigor'] = (1, 4, "Take the skies", "Gives all allied [dragon] minions your fired up! buff.") ##TODO modify, it's close to an existing upgrade

	def get_description(self):
		return ("Fears all non [Dragon] units for [{duration}:duration] turns, then Summon a Bookwyrm at your location. The Bookwyrm is a dragon whose breath deals:\n" 
				"[Fire], [Lightning], [Ice], [Arcane], [Holy], [Dark], [Poison], or [Physical] damage, while summoning scrolls that cast cantrips in empty squares."
				"The scrolls last 2 turns.").format(**self.fmt_dict())

	def get_extra_examine_tooltips(self):
		return [BookWyrm(), self.spell_upgrades[0], self.spell_upgrades[1], self.spell_upgrades[2]]

	def cast_instant(self, x, y):
		units = [u for u in self.caster.level.units if Tags.Dragon not in u.tags and not u.is_player_controlled]
		for unit in units:
			unit.apply_buff(FearBuff(), self.get_stat('duration'))
			
		if self.get_stat('double'):
			n = 2
		else:
			n = 1
		for i in range(n):
			unit = BookWyrm()
			apply_minion_bonuses(self, unit)
			self.summon(unit, Point(x, y))

		if self.get_stat('vigor'):
			temp_spell = self.caster.get_or_make_spell(FireEmUp)
			units = [u for u in self.caster.level.units if Tags.Dragon in u.tags]
			for unit in units:
				unit.apply_buff(FiredUp(temp_spell), temp_spell.get_stat('duration'))

	
# def BloodSlime():

# 	unit = Unit()

# 	unit.name = "Blood Slime"
# 	unit.asset = ["TcrsCustomModpack", "Units", "blood_slime"]
# 	unit.max_hp = 10

# 	unit.tags = [Tags.Slime, Tags.Blood]

# 	unit.spells.append(SimpleRangedAttack(damage=3, damage_type=Tags.Dark, range=3))
# 	unit.buffs.append(SlimeBuff(spawner=BloodSlime))

# 	unit.resists[Tags.Dark] = 50
# 	unit.resists[Tags.Physical] = 25
# 	unit.resists[Tags.Holy] = -25

# 	return unit

class Exsanguinate(Spell):
	
	def on_init(self):
		self.name = "Exsanguinate"
		self.tags = [Tags.Blood, Tags.Sorcery, Tags.Conjuration, Tags.Slime]
		self.asset = ["TcrsCustomModpack", "Icons", "exsanguinate"]
		self.level = 4 ##Considering level 4 and giving it a large charge reserve with a medium health cost. Maybe level 5 and buffing its range and damage?
		self.hp_cost = 10 #High hp cost and high charges?
		
		self.max_charges = 9
		self.damage = 20
		self.damage_type = [Tags.Dark, Tags.Poison]
		self.sum_dmg = {Tags.Dark:0,Tags.Poison:0,Tags.Arcane:0, Tags.Fire:0, Tags.Ice:0}
		self.range = 4
		self.minion_health = 10
		self.minion_damage = 3
		
		self.magus = 0
		self.example = BloodWizard()
		self.example.max_hp = 150
		self.slimes = {Tags.Poison:GreenSlime, Tags.Dark:BloodSlime, Tags.Arcane:VoidSlime, Tags.Fire:RedSlime, Tags.Ice:IceSlime}
		self.can_target_empty = False

		self.upgrades['frostfire'] = (1, 5, "Frostfire", "Adds [Fire] and [Ice] damage, and red slimes and ice slimes.", [Tags.Fire, Tags.Ice])
		self.upgrades['nightmare'] = (1, 2, "Nightmare", "Adds [Arcane] damage and void slimes.", [Tags.Arcane])
		self.upgrades['wizard'] = (1, 4, "Blood Magic", "For every 150 damage dealt by the spell, summon a blood magus for 25 turns.")
		#self.upgrades['slimeform'] = (1, 0, "Slime Coating", "When you cast the first or last charge of this spell, cast your slime form as well.") ##TODO implement

	def get_extra_examine_tooltips(self):
		return [BloodSlime(), GreenSlime(), self.spell_upgrades[0], RedSlime(), IceSlime(), self.spell_upgrades[1], VoidSlime(), self.spell_upgrades[2], self.example]

	def get_description(self):
		return ("Deal [{damage}_poison:poison] damage, then [{damage}_dark:dark] to one unit, " +
				"then summon a green slime or blood slime for each 10 [poison] or [dark] damage dealt by this spell.\n"
				"Slimes have [{minion_health}_HP:minion_health] and deal {minion_damage} damage.").format(**self.fmt_dict())

	def cast_instant(self, x, y):
		dtypes = list(self.damage_type)
		if self.get_stat('frostfire'):
			dtypes.append(Tags.Fire)
			dtypes.append(Tags.Ice)
		if self.get_stat('nightmare'):
			dtypes.append(Tags.Arcane)
		
		random.shuffle(dtypes)
		unit = self.caster.level.get_unit_at(x, y)
		for tag in dtypes:
			temp_damage = unit.deal_damage(self.get_stat('damage'), tag, self)
			self.sum_dmg[tag] += temp_damage
			if self.get_stat('wizard'):
				self.magus += temp_damage
		for tag in self.sum_dmg:
			while self.sum_dmg[tag] > 10:
				slime = self.slimes[tag]()
				apply_minion_bonuses(self, slime)
				self.summon(slime, Point(x,y), radius = 3,sort_dist=True)
				self.sum_dmg[tag] = self.sum_dmg[tag] - 10
				
		if self.get_stat('wizard'):
			while self.magus >= 150:
				u = BloodWizard()
				u.max_hp = 150
				u.turns_to_death = self.get_stat('minion_duration',base=25)
				apply_minion_bonuses(self,u)
				self.summon(u)
				self.magus -= 150

class GrotesqueBuff(Buff):
	def __init__(self, spell):
		self.spell = spell
		Buff.__init__(self)

	def on_init(self):
		self.name = "Statuification"
		self.color = Color(180, 180, 180)
		self.resists[Tags.Physical] = 50
		self.resists[Tags.Fire] = 50
		self.resists[Tags.Ice] = 50
		self.resists[Tags.Lightning] = 50
		self.buff_type = BUFF_TYPE_CURSE
		self.stack_type = STACK_REPLACE
		self.asset = ['status', 'stoned']
	
	def on_unapplied(self):
		if self.owner.is_alive() and self.turns_left == 0:
			self.spell.make_gargoyle(self.owner.x, self.owner.y)
		else:
			return
	
		
def GrotesqueStatue():
	unit = Unit()
	unit.name = "Crumbling Statue"
	unit.asset = ["TcrsCustomModpack", "Units", "grotesque_statue"]
	unit.max_hp = 30
	unit.tags = [Tags.Metallic, Tags.Construct, Tags.Dark]
	unit.resists[Tags.Dark] = 75
	unit.resists[Tags.Holy] = -50
	unit.stationary = True
	return unit

class Grotesquify(Spell):
	def on_init(self):
		self.name = "Statuesque Curse"
		self.tags = [Tags.Enchantment, Tags.Metallic]
		self.level = 2
		self.asset = ["TcrsCustomModpack", "Icons", "slow_petrify"]
		
		self.max_charges = 12
		self.duration = 1
		self.range = 8
		
		self.can_target_empty = False
		
		self.upgrades['gargoyle'] = (1, 3, "Grotesquery", "Enemies now also become a Gargoyle, or if it had more than 100 max hp, a Mega Gargoyle.")
		self.upgrades['group'] = (1, 5, "Connection", "Curses a group of connected enemies.")
		self.upgrades['eyes'] = (1, 2, "Watching Ornaments", "The transformed unit knows one of: Eye of Fire, Lightning, Ice, or Blood.", [Tags.Eye])

	def get_description(self):
		return ("Curses a unit to slowly petrify, granting the target 50% resistance to [Physical], [Fire], [Ice], and [Lightning] damage. "
				"When the curse ends, transform the unit into a statue.\n"
				"Allies turn into Gargoyles and enemies into Crumbling Statues.\n"
				"The curse lasts for 1 turn for each 10 max hp the target has, minus [{duration}_turns:duration], scaling with duration bonuses.\n"
				"Does not affect constructs.").format(**self.fmt_dict())
	
	def get_extra_examine_tooltips(self):
		return [Gargoyle(), GrotesqueStatue(), self.spell_upgrades[0], MegaGargoyle(), MegaGargoyleStatue(), self.spell_upgrades[1], self.spell_upgrades[2]]

	def cast_instant(self, x, y):
		tiles = self.get_impacted_tiles(x,y)
		for t in tiles:
			unit = self.caster.level.get_unit_at(t.x, t.y)
			if Tags.Construct in unit.tags:
				return
			duration = math.ceil(unit.max_hp / 10)
			duration -= self.get_stat('duration')
			if duration > 0:
				unit.apply_buff(GrotesqueBuff(self),duration)
			else:
				self.make_gargoyle(t.x, t.y)

	def make_gargoyle(self, x, y):
		p = Point(x, y)
		u = self.owner.level.get_unit_at(x, y)
		if u == None:
			return
		if self.get_stat('gargoyle') or not are_hostile(u, self.owner):
			if u.max_hp < 100:
				unit = Gargoyle()
			else:
				unit = MegaGargoyle()
		else:
			unit = GrotesqueStatue()
			unit.turns_to_death = 10
		if self.get_stat('eyes'):
			spell = random.choice([EyeOfFireSpell,EyeOfIceSpell,EyeOfLightningSpell, EyeOfBloodSpell])
			grant_minion_spell(spell, unit, self.owner, cool_down=15)
		unit.team = self.owner.team
		apply_minion_bonuses(self, unit)
		u.kill(trigger_death_event=False)
		self.owner.level.summon(self.owner, unit, p, team=unit.team)

	def get_impacted_tiles(self, x, y):
		tiles = [Point(x, y)]
		if self.get_stat('group'):
			tiles = self.caster.level.get_connected_group_from_point(x, y, check_hostile=self.caster)
		return tiles

def Tachi():
	unit = DancingBlade()
	unit.name = "Tachi"
	unit.asset = ["TcrsCustomModpack", "Units", "spectral_blade_amaterasu"]
	unit.max_hp = 45
	unit.shields = 2
	unit.spells[0].name = "Dancing Blade"
	unit.spells[0].damage = 12
	unit.spells[0].range = 6
	##unit.apply_buff(HasteKillVersion()) ##Buggy evaluate potential.
	return unit

class WordoftheSun(Spell):

	def on_init(self):
		self.name = "Word of Sunlight"
		self.asset = ["TcrsCustomModpack", "Icons", "word_of_the_sun"]
		self.tags = [Tags.Fire, Tags.Holy, Tags.Word]
		self.level = 7
		
		self.max_charges = 1
		self.damage = 25
		self.damage_type = [Tags.Fire]
		self.range = 0
		self.duration = 10

		self.self_target = True

		self.upgrades['aztec'] = (1, 2, "Tonatiuh", "Explodes all of your allies, dealing their current hp as fire damage in a 4 tile burst.",[Tags.Sorcery])
		self.upgrades['egyptian'] = (1, 3, "Ra-Horakhty", "Summons an avian wizard and a raven mage.",[Tags.Conjuration])
		self.upgrades['japanese'] = (1, 3, "Amaterasu", "Summons a powerful dancing blade which can leap and attack two times per turn.", [Tags.Conjuration])

	def get_extra_examine_tooltips(self):
		return [self.spell_upgrades[0], self.spell_upgrades[1], AvianWizard(), RavenMage(), self.spell_upgrades[2], Tachi()]

	def get_impacted_tiles(self, x, y):
		return [u for u in self.caster.level.units if u != self.caster]		

	def get_description(self):
		return ("Blinds all non [Holy] enemies for [{duration}_turns:duration]."
				"\nDeals [{damage}_fire:fire] damage to all [dark] units.\n"
				"Hastens all [fire] allies for 5 turns.").format(**self.fmt_dict())

	def cast(self, x, y, is_echo=False):
		if self.get_stat('japanese'):
			unit = Tachi()
			apply_minion_bonuses(self,unit)
			unit.apply_buff(HasteBuff())
			self.summon(unit, self.caster)
		if self.get_stat('egyptian'):
			avian = AvianWizard()
			apply_minion_bonuses(self, avian)
			self.summon(avian, self.caster)
			raven = RavenMage()
			apply_minion_bonuses(self, raven)
			self.summon(raven,self.caster)
		units = list(self.caster.level.units)
		random.shuffle(units)
		for unit in units:
			if self.get_stat('aztec') and not are_hostile(self.caster, unit) and unit != self.caster:
				self.caster.level.show_effect(unit.x, unit.y, Tags.Fire)
				unit.level.queue_spell(self.explode(unit))
			if Tags.Dark in unit.tags:
				unit.deal_damage(self.get_stat('damage'), Tags.Fire, self)
			if Tags.Holy not in unit.tags and are_hostile(self.caster, unit):
				unit.apply_buff(BlindBuff(), self.get_stat('duration'))
			if Tags.Fire in unit.tags and not are_hostile(self.caster, unit):
				unit.apply_buff(HasteBuff(), 5)
			yield

	def explode(self, unit):
		damage = unit.cur_hp
		unit.kill()
		units = self.caster.level.get_units_in_ball(Point(unit.x,unit.y), 4)
		for u in units:
			if are_hostile(unit, u):
				u.deal_damage(damage, Tags.Fire, self)
		yield

class WordofFilth(Spell):
	def on_init(self):
		self.name = "Word of Decay"
		self.tags = [Tags.Nature, Tags.Word]
		self.asset = ["TcrsCustomModpack", "Icons", "word_of_decay"]
		self.level = 7
		
		self.max_charges = 1
		self.range = 0
		self.minion_health = 25
		self.minion_duration = 7
		self.minion_damage = 7

		self.self_target = True
	
		self.upgrades['permanent'] = (1, 7, "Endurance", "Half of the units summoned are permanent units.",[Tags.Conjuration])
		self.upgrades['toxic'] = (1, 3, "Toxicity", "Poisons every unit on the map for 3 turns.")
		self.upgrades['undeath'] = (1, 2, "Undeath", "Applies your plague of undeath debuff to every enemy unit.",[Tags.Dark])

	def get_description(self):
		return ("All empty tiles on the map have a 10% chance to spawn a unit.\n"
				"Each chasm can spawn a fly cloud, each wall can spawn a rockworm, and each floor can spawn a mind maggot.\n"
				"The units last for a random number of turns between 1 and [{minion_duration}_turns:minion_duration].").format(**self.fmt_dict())

	def get_extra_examine_tooltips(self):
		return [self.make_flies(), self.make_worms(), self.make_maggots() ,self.spell_upgrades[0], self.spell_upgrades[1], self.spell_upgrades[2]]

	def make_flies(self):
		u = FlyCloud()
		u.max_hp = self.get_stat('minion_health') / 4
		u.spells[0].damage = self.get_stat('minion_damage') / 3
		return u

	def make_worms(self):
		u = RockWurm()
		u.max_hp = self.get_stat('minion_health')
		u.spells[0].damage = self.get_stat('minion_damage')
		return u

	def make_maggots(self):
		u = MindMaggot()
		u.max_hp = self.get_stat('minion_health') / 4
		u.spells[0].damage = self.get_stat('minion_damage') / 2
		return u

	def cast(self, x, y):
		if self.get_stat('toxic'):
			units = list(self.caster.level.units)
			for u in units:
				if u.resists[Tags.Poison] < 100:
					u.apply_buff(Poison(), 3)
		if self.get_stat('undeath'):
			units = list(self.caster.level.units)
			for u in units:
				if are_hostile(self.caster, u) and Tags.Living in u.tags:
					hallowflesh = self.caster.get_or_make_spell(Spells.HallowFlesh)
					buff = RotBuff(hallowflesh)
					buff.owner_triggers[EventOnDeath] = hallowflesh.make_zombie
					u.apply_buff(buff)
		tiles = self.caster.level.iter_tiles()
		for t in tiles:
			if random.random() > 0.90:
				u = None
				if self.caster.level.tiles[t.x][t.y].is_chasm:
					u=self.make_flies()
				elif self.caster.level.tiles[t.x][t.y].is_wall():
					self.caster.level.make_floor(t.x, t.y)
					u=self.make_worms()
				elif self.caster.level.tiles[t.x][t.y].is_floor():
					u=self.make_maggots()

				if u != None:
					duration = random.randint(1, self.get_stat('minion_duration'))
					if self.get_stat('permanent'):
						if random.random() > 0.50:
							u.turns_to_death = duration
					else:
						u.turns_to_death = duration
					self.summon(u,target=Point(t.x,t.y))
			yield
	
class HolyBeamBattery(Buff): ##TODO figure out a new way to store damage, interesting concept
	def __init__(self, prev):
		self.damage = prev // 2
		Buff.__init__(self)

	def on_init(self):
		self.buff_type = BUFF_TYPE_BLESS
		self.name = "Holy Battery"
		self.color = Tags.Holy.color
		self.owner_triggers[EventOnSpellCast] = self.on_cast
		self.spell_bonuses[HolyBeam]['damage'] = self.damage
		
	def on_cast(self, spell_cast_event):
		if spell_cast_event.spell.name == "Ray of Divinity":
			self.owner.remove_buff(self)


class HolyBeam(Spell):
	def on_init(self):
		self.name = "Ray of Divinity"
		self.tags = [Tags.Holy, Tags.Sorcery]
		self.asset = ["TcrsCustomModpack", "Icons", "holy_beam"]
		self.level = 4 ##Deals 80 + number of units damage, so it's as good as void beam on ~3 targets, and much weaker on 4+.

		self.max_charges = 6
		self.damage = 80
		self.damage_type = [Tags.Holy]
		self.range = 16

		self.requires_los = False

		self.upgrades['healing'] = (1, 2, "Healing Inversion", " Allied units are now healed instead of damaged, and add 20 damage to the beam when passed through.")
		self.upgrades['battery'] = (1, 3, "Shocking Twist", "At the beam's final point shoot a new [80:damage] damage [lightning] beam from the target to a random enemy unit.", [Tags.Lightning])
		self.upgrades['wallsucker'] = (1, 3,"Walleater", "Walls are now destroyed and add 20 damage to the beam when passed through.\n" +
											"If 4 or more walls are destroyed in one beam, shoot a new [80:damage] damage [arcane] beam from the target to a random enemy unit.", [Tags.Arcane])

	def get_description(self):
		return ("Deal [{damage}_holy:holy] damage in a beam. Pierces but does not destroy walls. The beam loses damage as it deals damage.\n"
				"Each unit strike subtracts the total damage dealt from the beam, and each wall passed subtracts 20 damage."
				"The minimum damage of the beam is 5.").format(**self.fmt_dict())

	def get_impacted_tiles(self, x, y):
		start = Point(self.caster.x, self.caster.y)
		target = Point(x, y)
		points = []
		path = Bolt(self.caster.level, start, target, two_pass=False, find_clear=False)
		for point in path:
			points.append(point)
		return points

	def shoot_beam(self, x, y, tag, start):
		cur_damage = self.get_stat('damage')
		wall_count = 0
		for p in Bolt(self.caster.level, start, Point(x, y),find_clear=False):
			if self.caster.level.tiles[p.x][p.y].is_wall():
				if self.get_stat('wallsucker'):
					self.caster.level.make_floor(p.x, p.y)
					cur_damage += 20
					wall_count += 1
				else:
					cur_damage -= 20

			if self.get_stat('healing'):
				unit = self.caster.level.get_unit_at(p.x, p.y)
				if unit != None:
					if not self.caster.level.are_hostile(self.caster, unit):
						cur_damage += 20
						self.caster.level.deal_damage(p.x, p.y, cur_damage * -1, Tags.Heal, self)
					else:
						cur_damage -= self.caster.level.deal_damage(p.x, p.y, cur_damage, tag, self)
				else:
					self.caster.level.show_effect(p.x, p.y, tag, minor=False)
			else:
				cur_damage -= self.caster.level.deal_damage(p.x, p.y, cur_damage, tag, self)
				
			if cur_damage <= 5:
				cur_damage = 5
		return wall_count

	def cast(self, x, y):
		walls = self.shoot_beam(x, y, Tags.Holy, Point(self.caster.x, self.caster.y))
		if self.get_stat('battery') or walls >= 4:
			targets = self.caster.level.get_units_in_ball(Point(x, y), self.get_stat('range'))
			targets = [t for t in targets if are_hostile(self.caster, t) and (t.x != x and t.y != y)]
			if targets == []:
				return
			random.shuffle(targets)
			new_p = targets[0]
			if walls >= 4:
				self.shoot_beam(new_p.x, new_p.y, Tags.Arcane, Point(x, y))
			else:
				self.shoot_beam(new_p.x, new_p.y, Tags.Lightning, Point(x, y))

		yield

				
# class MirrorShieldBuff_OLD(Buff):
# 	def __init__(self, spell):
# 		self.spell = spell
# 		Buff.__init__(self)

# 	def on_init(self):
# 		self.buff_type = BUFF_TYPE_BLESS
# 		self.name = "Mirror Shield"
# 		self.color = Tags.Arcane.color
# 		self.global_triggers[EventOnSpellCast] = self.on_cast
# 		self.stack_type = STACK_TYPE_TRANSFORM
# 		self.transform_asset = ["TcrsCustomModpack", "Units", "player_shielding"]
# 		self.description = "Shield yourself, and reflect most spells."
		
# 	def on_advance(self):
# 		if self.owner.shields <= 18:
# 			self.owner.shields += self.spell.get_stat('shields')
# 	def on_unapplied(self):
# 		self.owner.shields = 0

# 	def on_cast(self, evt):
# 		if evt.caster == self.owner and not evt.spell.added_by_buff:
# 			if distance(evt.caster, Point(evt.x, evt.y)) >= 1.5 and not self.spell.get_stat('far_field'):
# 				self.owner.shields = 0
# 				self.owner.remove_buff(self)
# 		if not are_hostile(evt.caster, self.owner):
# 			return
# 		spell = None
# 		if isinstance(evt.spell, LeapAttack):
# 			spell = SimpleMeleeAttack()
# 		if isinstance(evt.spell, BreathWeapon):
# 			spell = BreathWeapon()
# 		if isinstance(evt.spell, (SimpleMeleeAttack, SimpleRangedAttack)):
# 			spell = type(evt.spell)()
# 		if spell == None:
# 			return
# 		spell.caster = self.owner
# 		spell.owner = self.owner
# 		spell.added_by_buff = True
# 		spell.statholder = self.owner
# 		spell.damage = evt.spell.damage
# 		spell.buff = evt.spell.buff
# 		spell.buff_duration = evt.spell.buff_duration
# 		spell.buff_name = evt.spell.buff().name if spell.buff else None
# 		if isinstance(evt.spell.damage_type, list):
# 			damage_type = random.choice(evt.spell.damage_type)
# 		else:
# 			damage_type = evt.spell.damage_type
# 		if self.spell.get_stat('adaptive'):
# 			spell.damage += self.spell.get_stat('damage', base=5)
# 			if evt.caster.resists[damage_type] >= 100:
# 				if evt.caster.resists[Tags.Physical] >= 100:
# 					damage_type = Tags.Arcane
# 				else:
# 					damage_type = Tags.Physical
# 		else:
# 			damage_type = evt.spell.damage_type
# 		spell.damage_type = damage_type
# 		## If onhit was copied it would cause a lot of possible problems, draining max hp lmao
# 		spell.name = "Reflected Attack"
# 		self.owner.level.act_cast(self.owner, spell, evt.caster.x, evt.caster.y, pay_costs=False)
# 		self.owner.level.show_effect(evt.caster.x, evt.caster.y, Tags.Arcane, minor=False)
		
# 			# dtype = self.damage_type
# 			# if isinstance(dtype, list):
# 			# 	dtype = random.choice(dtype)

class MirrorShieldBuff(Buff):
	def __init__(self, spell):
		self.spell = spell
		Buff.__init__(self)

	def on_init(self):
		self.buff_type = BUFF_TYPE_BLESS
		self.name = "Mirror Shield"
		self.color = Tags.Arcane.color
		self.global_triggers[EventOnSpellCast] = self.on_cast
		self.stack_type = STACK_TYPE_TRANSFORM
		self.transform_asset = ["TcrsCustomModpack", "Units", "player_shielding"]
		self.description = "Shield yourself, and absorb damage from spells.\nCharges: 0"
		self.damage_total = 0
	
	def on_pre_advance(self):
		self.description = "Shield yourself, and absorb damage from spells.\nCharges: " + str(self.damage_total)

	def on_advance(self):
		shields = self.spell.get_stat('shields')
		if self.spell.get_stat('retention'):
			shields += 1
		if self.owner.shields + shields <= 20:
			self.owner.shields += shields
		else:
			self.owner.shields = 20
		self.description = "Shield yourself, and absorb damage from spells.\nCharges: " + str(self.damage_total)
			
	def on_unapplied(self):
		if self.spell.get_stat('retention'):
			if self.owner.shields > 3:
				self.owner.shields = 3
		else:
			self.owner.shields = 0
		radius = self.spell.get_stat('radius')
		radius += self.damage_total // 50
		points = self.owner.level.get_points_in_ball(self.owner.x, self.owner.y, radius)
		for p in points:
			if p.x == self.owner.x and p.y == self.owner.y:
				continue
			self.owner.level.deal_damage(p.x, p.y, self.spell.get_stat('damage'), Tags.Arcane, self)
		
	def on_cast(self, evt):
		if evt.caster == self.owner and distance(evt.caster, Point(evt.x, evt.y)) <= 1.5 and self.spell.get_stat('bash'):
			if self.owner.x == evt.x and self.owner.y == evt.y:
				return
			else:
				self.owner.level.deal_damage(evt.x, evt.y, self.damage_total * 2, Tags.Physical, self)
				
		if not are_hostile(evt.caster, self.owner):
			return
		if hasattr(evt.spell,'damage'):
			self.damage_total += evt.spell.damage

class ShieldAbsorption(Upgrade):
	def on_init(self):
		self.level = 4
		self.name = "Absorption"
		self.description = "Whenever you block any damage with a shield, your next Mirror Shield starts with 5 charges per attack blocked."
		self.global_triggers[EventOnShieldRemoved] = self.on_shield_hit
		self.owner_triggers[EventOnBuffApply] = self.on_buff
		self.bonus_charges = 0

	def on_shield_hit(self, evt):
		if evt.unit != self.owner:
			return
		self.bonus_charges += 5

	def on_buff(self, evt):
		if isinstance(evt.buff, MirrorShieldBuff):
			evt.buff.damage_total += self.bonus_charges
			evt.buff.description = "Shield yourself, and absorb damage from spells.\nCharges: " + str(evt.buff.damage_total)
			self.bonus_charges = 0

class MirrorShield(Spell):
	def on_init(self):
		self.name = "Mirror Shield"
		self.asset = ["TcrsCustomModpack", "Icons", "mirror_shield"]
		self.level = 5
		self.tags = [Tags.Arcane, Tags.Enchantment, Tags.Metallic]
		
		self.max_charges = 5
		self.damage = 40
		self.damage_type = [Tags.Arcane]
		self.range = 0
		self.radius = 4
		self.duration = 5
		
		self.shields = 2
		self.can_target_self = True
		self.max_channel = 10

		self.add_upgrade(ShieldAbsorption())
		self.upgrades['bash'] = (1, 3, "Shield Bash", "If you cast a spell on an adjacent tile while you have the buff, deal [physical] damage to the tile equal to the buff's charges.")
		self.upgrades['retention'] = (1, 4, "Barrier", "Keep up to 3 shields when the buff is removed, and the buff grants 3 shields per turn instead of 2.")
		
	def get_description(self):
		return ("Gain the Mirror Shield buff [{duration}_turns:duration] turns, and gain 1 turn if you channel.\n"
				"The buff grants [2_shields:shields] each turn, and gets charges equal to the damage stat of spells that target you.\n"
				"When the buff is removed, you lose all shields and deal [{damage}_arcane:arcane] damage to enemies in a [{radius}_tile:radius] tile burst, gaining 1 radius for every 50 charges the buff had.").format(**self.fmt_dict())

	def cast(self, x, y, channel_cast=False):
		if not channel_cast:
			self.caster.apply_buff(ChannelBuff(self.cast, Point(x, y)), self.get_stat('max_channel'))
			return
		buff = self.caster.get_buff(MirrorShieldBuff)
		if buff == None:
			self.caster.apply_buff(MirrorShieldBuff(self), self.get_stat('duration'))
		else:
			if self.get_stat('extend'):
				buff.turns_left += self.get_stat('duration')
			else:
				buff.turns_left += 1
		yield

	def get_impacted_tiles(self, x, y):
		buff = self.caster.get_buff(MirrorShieldBuff)
		if buff == None:
			return [Point(x, y)]
		else:
			return self.caster.level.get_points_in_ball(self.caster.x, self.caster.y, self.get_stat('radius'))

def AmalgamateUnit(hp=127, spell=None):
	unit = Unit()
	unit.name = "Amalgamation"
	unit.max_hp = hp
	if unit.max_hp <= 24:
		unit.asset = ["TcrsCustomModpack", "Units", "amalgamate_small"]
	elif unit.max_hp <= 120:
		unit.asset = ["TcrsCustomModpack", "Units", "amalgamate_med"]
	else:
		unit.asset = ["TcrsCustomModpack", "Units", "amalgamate_large"] #Credit to K.Hoops for the flesh fiend sprite. Its mouth serves as the basis for all amalgams.
	unit.buffs.append(RegenBuff(unit.max_hp//10))
	unit.tags = [Tags.Living, Tags.Construct]
	if spell == None:
		bonus_tag1 = random.choice([Tags.Fire, Tags.Ice, Tags.Lightning, Tags.Arcane, Tags.Dark])
		unit.tags.append(bonus_tag1)
		unit.spells.append(SimpleRangedAttack(damage=15,damage_type=bonus_tag1,range=3,cool_down=1))
		bonus_tag2 = random.choice([Tags.Fire, Tags.Ice, Tags.Lightning, Tags.Arcane, Tags.Dark])
		unit.spells.append(SimpleMeleeAttack(damage=15,damage_type=bonus_tag2,attacks=2))
		bonus_tag3 = random.choice([Tags.Metallic, Tags.Chaos, Tags.Poison, Tags.Dragon, Tags.Undead])
		unit.tags.append(bonus_tag3)

	unit.resists[Tags.Physical] = -50
	unit.resists[Tags.Poison] = -50

	return unit

##Cross Stich -> Same kind of effect in a line instead of connected. Works through walls? Turns walls into hp lol?
class Amalgamate(Spell): ## Implement some variation of this spell, after the main branch has basically obseleted it lol
	def on_init(self):
		self.name = "Cross Stich"
		self.tags = [Tags.Dark, Tags.Conjuration, Tags.Enchantment]
		self.asset =  ["TcrsCustomModpack", "Icons", "amalgamate_icon"]
		self.level = 7 ##Level 4? 5? Comparisons are mass calcification (converts max hp of all units into bone shambers, so similar to amalgamating your whole army)
		##Produces extremely powerful units but they can only take 1 action per turn, would likely decrease overall DPS (reevaluation with new upgrades, seems fun but may be too strong)
		
		self.max_charges = 4
		self.minion_health = 10
		self.range = 8
		self.radius = 10
		
		self.can_target_empty = False
		self.viable_tags = [Tags.Living, Tags.Nature, Tags.Undead]
		
		self.upgrades['elemental'] = (1, 3, "Elemental", "Adds Fire, Lightning, Ice as viable tags. Its ranged attacks get 1 radius.")
		self.upgrades['ethereal'] = (1, 2, "Ethereal", "Adds Arcane, Holy, Dark, and Demon as viable tags. Its leap attacks gain 3 range.", [Tags.Arcane])
		self.upgrades['creature'] = (1, 3, "The Creature", "Adds Metallic, Construct, Glass, and Slime as viable tags. Its melee attack hits twice.",[Tags.Metallic])
		#self.upgrades['strange'] = (1, 0, "Strange", "Adds Dragon, Chaos, Slime, whatever as viable tags. Can learn breath attacks.")

	def get_description(self):
		return ("Amalgamates all [Living], [Nature], or [Undead] units in a 10 tile cross, killing any allies, and stealing [{minion_health}_max_hp:minion_health] from enemies.\n"
				"Then spawn an Amalgamation at the target location, with the total max hp of allies, the stolen hp of enemies, and all of their tags and simple spells.\n"
				"Simple spells are melee attacks, leaps, and most ranged attacks. Combines their damage stat, and uses the base ."
				"The Amalgamation regenerates 10% of its base max hp each turn.").format(**self.fmt_dict())

	def get_impacted_tiles(self, x, y):
		rad = self.get_stat('radius')
		for i in range(-rad, rad + 1):
			yield Point(x+i, y)
			if i != 0:
				yield Point(x, y+i)

	def cast_instant(self, x, y):
		points = self.get_impacted_tiles(x, y)
		max_hp = 1
		targ_tags = [Tags.Living, Tags.Nature, Tags.Undead]
		if self.get_stat('elemental'):
			targ_tags.extend( [Tags.Fire, Tags.Ice, Tags.Lightning] )
		if self.get_stat('ethereal'):
			targ_tags.extend( [Tags.Arcane, Tags.Holy, Tags.Dark, Tags.Demon] )
		if self.get_stat('creature'):
			targ_tags.extend( [Tags.Metallic, Tags.Construct, Tags.Glass, Tags.Slime] )
		amalg_tags = [Tags.Living, Tags.Construct]
		amalg_spells = {}
		
		for p in points:
			unit = self.caster.level.get_unit_at(p.x, p.y)
			if unit == None:
				continue
			if unit == self.caster:
				continue
			if not any(unit.tags and targ_tags):
				continue
			
			for tag in unit.tags:
				if tag not in amalg_tags:
					amalg_tags.append(tag)
			max_hp += unit.max_hp
			for s in unit.spells:
				if not isinstance(s, (SimpleMeleeAttack, SimpleRangedAttack, LeapAttack)):
					continue
				if not hasattr(s,'damage'):
					continue
				if s.name in amalg_spells:
					amalg_spells[s.name].damage += s.damage
					if amalg_spells[s.name].range < s.range:
						amalg_spells[s.name].range = s.range
					if hasattr(amalg_spells[s.name], 'radius'):
						if amalg_spells[s.name].radius < s.radius:
							amalg_spells[s.name].radius = s.radius
				else:
					if type(s) == LeapAttack or type(s):
						amalg_spells[s.name] = type(s)(damage=s.damage, damage_type=s.damage_type, range=s.range)
					elif type(s) == SimpleRangedAttack:
						amalg_spells[s.name] = type(s)(damage=s.damage, damage_type=s.damage_type, range=s.range, radius=s.radius)
					else:
						amalg_spells[s.name] = type(s)(damage=s.damage, damage_type=s.damage_type)
					amalg_spells[s.name].name = s.name
			self.caster.level.show_effect(unit.x, unit.y, Tags.Dark, minor=False)
			
			if are_hostile(self.caster, unit):
				hp = self.get_stat('minion_health')
				if unit.max_hp <= hp:
					hp = unit.max_hp
				max_hp += hp
				unit.max_hp -= hp
				unit.cur_hp -= hp
				if unit.cur_hp <= 0:
					unit.kill()
			else:
				unit.kill()
		
		amalg = AmalgamateUnit(max_hp, self)
		amalg.tags = amalg_tags
		if amalg.max_hp == 1:
			return
		for k in amalg_spells:
			if isinstance(amalg_spells[k], SimpleMeleeAttack) and self.get_stat('creature'):
				amalg_spells[k].attacks = 2
			if isinstance(amalg_spells[k], SimpleRangedAttack) and self.get_stat('elemental'):
				amalg_spells[k].radius = 1
			if isinstance(amalg_spells[k], LeapAttack) and self.get_stat('ethereal'):
				amalg_spells[k].range += 3
			amalg.spells.append(amalg_spells[k])
		amalg.spells.sort(key=lambda s : getattr(s, 'damage', 0), reverse=True) ##Just like the other amalgamate, because I'm annoyed when a 3 hp melee attack is being used over my 42 damage lightning attack)
		
		if self.caster.level.tiles[x][y].is_chasm:
			amalg.flying = True

		self.caster.level.summon(self.caster, amalg, Point(x,y))

	# def get_impacted_tiles_OLD(self, x, y):
	# 	candidates = set([Point(x, y)])
	# 	unit_group = set()
	# 	if self.get_stat('elemental'):
	# 		tags = [Tags.Fire, Tags.Ice, Tags.Lightning]
	# 		for t in tags:
	# 			self.viable_tags.append(t)
	# 	if self.get_stat('ethereal'):
	# 		tags = [Tags.Arcane, Tags.Holy, Tags.Dark, Tags.Demon]
	# 		for t in tags:
	# 			self.viable_tags.append(t)
	# 	if self.get_stat('creature'):
	# 		tags = [Tags.Metallic, Tags.Construct, Tags.Glass, Tags.Slime]
	# 		for t in tags:
	# 			self.viable_tags.append(t)
	# 	while candidates:
	# 		candidate = candidates.pop()
	# 		unit = self.caster.level.get_unit_at(candidate.x, candidate.y)
	# 		if unit and unit not in unit_group:
	# 			if self.caster.level.are_hostile(self.caster, unit) and not self.get_stat('devour'):
	# 				continue
				
	# 			viable = False
	# 			for tag in unit.tags:
	# 				if tag in self.viable_tags:
	# 					viable = True
	# 			if not viable:
	# 				continue

	# 			unit_group.add(unit)

	# 			for p in self.caster.level.get_adjacent_points(Point(unit.x, unit.y), filter_walkable=False):
	# 				candidates.add(p)

	# 	return list(unit_group)


class OccultBlast(Spell):
	def on_init(self):
		self.name = "Occult Blast"
		self.tags = [Tags.Dark, Tags.Holy, Tags.Arcane, Tags.Sorcery, Tags.Blood] ##Maybe remove blood? Though it functions very differently from drain pulse.
		self.asset = ["TcrsCustomModpack", "Icons", "occult_blast"]
		self.level = 5 ##Level 5-6. Its self-damage is extremely high so it's a bit situational. You'll almost treat it like a blood spell.
		##When its radius doesn't grow it's quite reasonable, dealing less damage and having less aoe than flame burst and drain pulse. If you have an ally-maker staff though...
		
		self.max_charges = 5
		self.damage = 25
		self.damage_type = [Tags.Dark, Tags.Holy, Tags.Arcane]
		self.radius = 7
		self.range = 0
		
		self.upgrades['purestriker'] = (1, 5, "Purestriker", "No longer deals dark damage, but gains 1 radius for each enemy killed.")
		self.upgrades['nightmare'] = (1, 5, "Nightmarish Blast", "No longer deals holy damage, but gains 3 radius for each ally killed.")
		self.upgrades['twilight'] = (1, 2, "Twilight", "No longer deals arcane damage, and no longer deals self-damage.")
		self.upgrades['spirits'] = (1, 4, "Call Spirits", "Units killed summon a ghost of that element in the ring. The caster pays 1 hp for each ghost summoned, which can be fatal.",[Tags.Conjuration])

	def get_description(self):
		return ("Deal {damage} [Dark], [Holy], or [Arcane] in concentric rings around the caster, 1 for each radius. The damage cycles between the three types for each ring.\n" +
				"For each ally killed the ring expands by 1 more radius.\nThe caster pays 2 hp for each ring, which can be fatal.").format(**self.fmt_dict())

	def cast(self,x,y):
		if self.get_stat('purestrike'):
			self.damage_type = [Tags.Holy, Tags.Arcane]
		elif self.get_stat('nightmare'):
			self.damage_type = [Tags.Dark, Tags.Arcane]
		elif self.get_stat('twilight'):
			self.damage_type = [Tags.Holy, Tags.Dark]
		index_dtype = random.randint(0,len(self.damage_type)-1)
		
		temp_radius = 1
		final_radius = self.get_stat('radius')
		while temp_radius <= final_radius:
			dtype = self.damage_type[index_dtype]
			points = self.caster.level.get_points_in_ball(self.caster.x, self.caster.y, temp_radius)
			points = [p for p in points if p != Point(self.caster.x, self.caster.y) and distance(self.caster, p) >= temp_radius - 1]
			for p in points:
				unit = self.caster.level.get_unit_at(p.x,p.y)
				self.caster.level.deal_damage(p.x, p.y, self.get_stat('damage'), dtype, self)
				if unit and not unit.is_alive():
					if not are_hostile(self.caster, unit):
						if self.get_stat('nightmare'):
							final_radius += 2
						final_radius += 1
					if self.get_stat('purestrike') and are_hostile(self.caster, unit):
						final_radius += 1
					if self.get_stat('spirits'):
						self.summon(self.make_ghost(dtype),p)
						self.caster.level.event_manager.raise_event(EventOnSpendHP(self.caster, 1), self.caster) ##TODO make these 2 actually pay HP

			if not self.get_stat('twilight'):
				self.caster.level.event_manager.raise_event(EventOnSpendHP(self.caster, 2), self.caster)
			temp_radius += 1
			index_dtype += 1
			if index_dtype >= len(self.damage_type):
				index_dtype = 0
		yield

	def make_ghost(self, dtype): ##Can make this a dictionary, but it's a miniscule amount of optimization.
		if dtype == Tags.Arcane:
			unit = GhostVoid()
		elif dtype == Tags.Dark:
			unit = DeathGhost()
		elif dtype == Tags.Holy:
			unit = HolyGhost()
		apply_minion_bonuses(self, unit)
		return unit

	def get_impacted_tiles(self, x, y):
		points = self.caster.level.get_points_in_ball(self.caster.x, self.caster.y, self.radius)
		return points

def Fishman():
	unit = Unit()
	unit.max_hp = 25

	unit.name = "Fishman"
	unit.asset = ["TcrsCustomModpack", "Units", "fishman"] #Credit to K.Hoops' Stonefish sprite as the general fish design in RW
	unit.tags = [Tags.Living, Tags.Dark]

	unit.spells.append(SimpleMeleeAttack(8))
	
	unit.resists[Tags.Lightning] = -50
	unit.resists[Tags.Fire] = -50
	unit.resists[Tags.Ice] = -50
	unit.resists[Tags.Holy] = -50

	return unit

def FishmanCat():
	unit = Fishman()
	unit.name = "Catfishman"
	unit.asset = ["TcrsCustomModpack", "Units", "fishmancat"] #Catfish have the same colour scheme as accursed cats

	unit.spells[0] = (SimpleMeleeAttack(damage=8,damage_type=Tags.Dark))
	unit.buffs.append(ReincarnationBuff(1))
	unit.resists[Tags.Dark] = 100
	unit.resists[Tags.Holy] = -100

	return unit

def FishmanArcher():
	unit = Fishman()
	unit.name = "Archerfish Man"
	unit.asset = ["TcrsCustomModpack", "Units", "fishmanarcher"]
	unit.tags.append(Tags.Ice)

	unit.spells[0] = (SimpleRangedAttack(damage=8, damage_type=Tags.Ice, cool_down=2, range=10,proj_name="kobold_arrow_long"))
	unit.resists[Tags.Ice] = 50

	return unit

def FishmanLion():
	unit = Fishman()
	unit.name = "Lionfish Man"
	unit.asset = ["TcrsCustomModpack", "Units", "fishmanlion"]
	unit.tags.append(Tags.Nature)

	unit.buffs.append(Thorns(80,Tags.Poison))

	return unit

class IdolDepthsFishBuff(Buff):
	def __init__(self, idol_spell, parent_spell):
		self.idol_spell = idol_spell
		self.parent_spell = parent_spell
		Buff.__init__(self)

	def on_init(self):
		self.color = Tags.Dark.color
		self.name = "Fishification"
		#status.asset
		self.owner_triggers[EventOnDeath] = self.on_death

	def on_death(self, evt):
		unit = self.parent_spell.get_fish()
		unit.team = self.parent_spell.caster.team
		unit.max_hp = self.owner.max_hp
		min_hp = self.parent_spell.get_stat('minion_health')
		if unit.max_hp < min_hp:
			unit.max_hp = min_hp
		apply_minion_bonuses(self.parent_spell,unit)
		self.parent_spell.summon(unit, self.owner)

class Fishification(Spell):
	def __init__(self, parent_spell):
		self.parent_spell = parent_spell
		Spell.__init__(self)

	def on_init(self):
		self.name = "Fishification"
		self.range = 0

	def can_threaten(self, x, y):
		return False

	def get_description(self):
		return "Causes a random enemy to spawn a fishman on death."

	def get_ai_target(self):
		candidates = [u for u in self.caster.level.units if are_hostile(u, self.caster) and not u.has_buff(IdolDepthsFishBuff)]
		if not candidates:
			return None
		return random.choice(candidates)

	def can_cast(self, x, y):
		return True

	def cast_instant(self, x, y):
		unit = self.caster.level.get_unit_at(x, y)
		if not unit:
			return

		buff = IdolDepthsFishBuff(self, self.parent_spell)
		unit.apply_buff(buff)

		self.caster.level.show_path_effect(self.caster, unit, Tags.Dark, minor=True)

def IdolDepths():
	idol = Idol()
	idol.name = "Idol of the Depths"
	idol.asset = ["TcrsCustomModpack", "Units", "idol_of_depths"]
	idol.resists[Tags.Dark] = 100
	return idol

class RingofFishmen(Spell):
		
	def on_init(self):
		self.name = "Fishmen's Dance"
		self.tags = [Tags.Dark, Tags.Conjuration]
		if water_tag in Tags:
			self.tags.append(Tags.Water)
		self.asset = ["TcrsCustomModpack", "Icons", "idol_of_depths_icon"]
		self.level = 5 #Level 5 probably? Similar to flock of eagles + mini restless dead
		
		self.max_charges = 1
		self.range = 3
		self.minion_health = 25
		self.minion_damage = 8
		self.num_summons = 4
		
		self.must_target_empty = True
		self.must_target_walkable = True

		self.upgrades['archerfish'] = (1, 4, "Archerfish", "Fishmen are replaced by Archerfish men which have long ranged ice attack with a cooldown.",[Tags.Ice])
		self.upgrades['catfish'] = (1, 2, "Catfish", "Fishmen are replaced by Catfish men which reincarnate once upon dying, and deal dark damage.")
		self.upgrades['lionfish'] = (1, 3, "Lionfish", "Fishmen are replaced by Lionfish, which deal 80 [poison] damage to melee attackers.", [Tags.Nature])

	def get_extra_examine_tooltips(self):
		return [IdolDepths(), Fishman(), self.spell_upgrades[0], FishmanArcher(), self.spell_upgrades[1], FishmanCat(), self.spell_upgrades[2], FishmanLion()]

	def get_description(self):
		return ("Summons [{num_summons}:num_summons] fishmen, who are worshipping an Idol of the Depths.\n"
				"The Idol debuffs one random enemy each turn causing it to spawn a fishman on death. "
				"Each fishman has the max hp of the enemy that spawned it, with a minimum of [{minion_health}_HP:minion_health],"
				"and deals [{minion_damage}_physical:physical] damage in melee.").format(**self.fmt_dict())

	def get_impacted_tiles(self, x, y):
		return self.caster.level.get_points_in_rect(x-1, y-1, x+1, y+1)
	
	def cast(self, x, y):
		idol = IdolDepths()
		idol.spells.append(Fishification(self))
		self.summon(idol, Point(x,y))
		points = self.get_impacted_tiles(x,y)
		randp = []
		for p in points:
			randp.append(p)
		for i in range(self.get_stat('num_summons')):
			u = self.get_fish()
			apply_minion_bonuses(self, u)
			self.summon(u, random.choice(randp))
		yield

	def get_fish(self):
		if self.get_stat('lionfish'):
			unit = FishmanLion()
		elif self.get_stat('catfish'):
			unit = FishmanCat()
		elif self.get_stat('archerfish'):
			unit = FishmanArcher()
		else:
			unit = Fishman()
		if water_tag in Tags:
			unit.tags.append(Tags.Water)
		return unit

class HasteDamageVersion(Buff):
	def on_init(self):
		self.name = "Rage Awakened"
		self.buff_type = BUFF_TYPE_BLESS
		self.color = Tags.Chaos.color
		self.stack_type = STACK_NONE
		self.description = "Takes a turn whenever it takes damage."
		self.asset = ["TcrsCustomModpack", "Icons", "buff_haste"]
		self.owner_triggers[EventOnDamaged] = self.on_damage

	def on_damage(self, damage_event):
		if not damage_event.unit.cur_hp > 0:
			return
		if self.owner.is_alive():
			self.owner.advance()

class BerserkerCompletionDamage(Buff):
	def on_init(self):
		self.name = "Dying"
		self.buff_type = BUFF_TYPE_CURSE
		self.color = Tags.Chaos.color
		self.stack_type = STACK_NONE
		self.buff_type = BUFF_TYPE_PASSIVE
		self.asset = ["TcrsCustomModpack", "Icons", "buff_haste"]
		self.global_triggers[EventOnLevelComplete] = self.finished

	def on_advance_trigger(self):
		self.owner.cur_hp -= 13
		self.owner.max_hp -= 13
		if self.owner.max_hp <= 0 or self.owner.cur_hp <= 0:
			self.owner.kill()

	def finished(self, evt):
		self.on_advance = self.on_advance_trigger

def Berserker():
	unit = Unit()
	unit.asset = ["TcrsCustomModpack", "Units", "berserker"]
	unit.sprite.char = 'B'
	unit.sprite.color = Color(255, 110, 100)
	unit.name = "Berserker"
	unit.description = "A crazed demon which attacks friend and foe."
	unit.max_hp = 113
	unit.buffs.append(BerserkerCompletionDamage())
	unit.spells.append(SimpleMeleeAttack(damage=14))
	unit.spells.append(LeapAttack(damage=14, damage_type=Tags.Physical, range=8, is_leap=False))
	unit.tags = [Tags.Demon, Tags.Chaos]
	return unit

class CallBerserker(Spell):
	def on_init(self):
		self.name = "Call Berserker"
		self.tags = [Tags.Chaos, Tags.Conjuration]
		self.asset = ["TcrsCustomModpack", "Icons", "berserker_icon"]
		self.level = 2 ##Unbelievably well stated for its level, don't use it where it can hit you. Level 3? It's much stronger than bear
		
		self.max_charges = 6
		self.range = 13
		self.minion_health = 113
		self.minion_damage = 13
		self.minion_range = 8
		
		self.must_target_walkable = True

		self.upgrades['requires_los'] = (-1, 2, "Blindcasting", "Call Berserker can be cast without line of sight")
		self.upgrades['haste'] = (1, 2, "Rage Awakened", "The berserker takes a turn when it takes damage.")
		self.upgrades[('temporary', 'minion_duration')] = ([1, 1], 4, "Pacification", "The berserk status now lasts for 10 turns instead of being permanent. Minion duration lowers this duration, to a minimum of 1.")


	def get_extra_examine_tooltips(self):
		return [Berserker(), self.spell_upgrades[0], self.spell_upgrades[1], self.spell_upgrades[2]]

	def get_description(self):
		return ("Summon a berserker, a crazed [demon] which is permanently berserk.\n"
				"The Berserker has [{minion_health}_HP:minion_health] and deals [{minion_damage}_physical:physical] damage with its attacks.\n"
				"The Berserker has both a charging attack with a range of [{minion_range}_tiles:minion_range] and a melee attack.\n"
				"The Berserker will continue fighting after the realm is cleared, but will lose 13 max hp each turn.\nIt will attack you.").format(**self.fmt_dict())
				##Clicking somewhere after realms are cleared will make you autowalk and the berserker will kill you instantly. (identical problem to fenris)

	def cast(self, x, y):
		unit = Berserker()
		if self.get_stat('haste'):
			unit.apply_buff(HasteDamageVersion())
		apply_minion_bonuses(self, unit)
		unit.turns_to_death = None
		self.summon(unit,Point(x,y))
		if self.get_stat('temporary'):
			#duration_bonus = self.get_stat('duration', base=10)
			minion_duration = self.get_stat('minion_duration', base=10)
			duration = 20 - minion_duration
			if duration <= 0:
				duration = 1
		else:
			duration = 0
		unit.apply_buff(BerserkBuff(), duration)

		#u = self.caster.level.get_unit_at(x, y)
		#if u.name == "Berserker":
		#	u.remove_buff(BerserkBuff)

		yield

class ChaosBolt(Spell):
	def on_init(self):
		self.name = "Fracture Bolt"
		self.tags = [Tags.Chaos, Tags.Sorcery]
		self.level = 3 ##Trying to aim for level 3, to make a level 3 chaos spell as there are only level 2 and 4.
		self.asset = ["TcrsCustomModpack", "Icons", "chaosbolt"]

		self.max_charges = 15
		self.damage = 12
		self.damage_type = [Tags.Physical, Tags.Fire, Tags.Lightning]
		self.range = 11
		self.radius = 4

		self.upgrades['imp'] = (1, 3, "Improviser", "Casts your Improvise at enemy units instead of arcing.") ##Very strong with swarm improviser, perhaps increase cost?
		self.upgrades['nightmare'] = (1, 3, "Comprehensive", "Add [Arcane] and [Dark] damage types.",[Tags.Dark, Tags.Arcane])
		self.upgrades['sacred'] = (1, 3, "Sacred", "Add [Ice] and [Holy] damage types.",[Tags.Ice, Tags.Holy])

	def get_description(self):
		return ("Shoots a bolt of chaotic energy in a line. The bolt deals {damage} [fire], [lightning], or [physical] to units, "
				"and each unit in the bolt's path arcs a separate bolt within [{radius}_tile:radius] to one more unit.").format(**self.fmt_dict())

	def cast(self, x, y):
		tiles = self.get_impacted_tiles(x,y)
		dtypes = [Tags.Fire, Tags.Lightning, Tags.Physical]
		if self.get_stat('nightmare'):
			dtypes.append(Tags.Arcane)
			dtypes.append(Tags.Dark)
		if self.get_stat('sacred'):
			dtypes.append(Tags.Holy)
			dtypes.append(Tags.Ice)
		units = []
		for t in tiles:
			dtype = random.choice(dtypes)
			u = self.caster.level.get_unit_at(t.x,t.y)
			if u != None:
				start = Point(u.x, u.y)
				all_targets = self.caster.level.get_units_in_ball(u, self.get_stat('radius'))
				targets = [targ for targ in all_targets if are_hostile(self.caster, targ) and not targ == u]
				if targets == []:
					end = Point(u.x + random.randint(-2,2), u.y + random.randint(-2,2))
					if self.caster.level.is_point_in_bounds(end):
						line = self.caster.level.get_points_in_line(start, end)
					else:
						line = None
				else:
					rand_targ = random.choice(targets)
					end = Point(rand_targ.x, rand_targ.y)
					line = self.caster.level.get_points_in_line(start, end)
					
				if self.get_stat('imp') and are_hostile(self.caster, u):
					spell = self.caster.get_or_make_spell(Improvise)
					self.caster.level.act_cast(self.caster, spell, u.x, u.y, pay_costs=False)
					if targets != []:
						self.caster.level.act_cast(self.caster, spell, end.x, end.y, pay_costs=False)
				else:
					if line:
						for tile in line:
							self.caster.level.deal_damage(tile.x, tile.y, self.get_stat('damage'), dtype, self)
			else: 
				if random.random() > 0.50: ##Just for visuals
					self.caster.level.show_effect(t.x, t.y, dtype, minor=True)
					end = Point(t.x + random.randint(0, 2), t.y + random.randint(0, 2))
					if self.caster.level.is_point_in_bounds(end):
						self.caster.level.show_effect(end.x, end.y, dtype, minor=True)
		yield

	def get_impacted_tiles(self, x, y):
		start = Point(self.caster.x, self.caster.y)
		target = Point(x, y)
		return list(Bolt(self.caster.level, start, target))

class MachinationBuff(Buff):
	def __init__(self, spell):
		self.spell = spell
		self.damage = 0
		Buff.__init__(self)

	def on_init(self):
		self.name = "Accumulation"
		self.buff_type = BUFF_TYPE_CURSE
		self.color = Tags.Metallic.color
		self.stack_type = STACK_REPLACE
		self.owner_triggers[EventOnDeath] = self.on_death
		self.owner_triggers[EventOnDamaged] = self.on_damage
		
	def on_damage(self, evt):
		if evt.unit == self.owner and not evt.source == self.spell:
			self.damage += evt.damage
		
	def on_death(self, evt):
		#print("Creating constructs out of: " + str(self.owner.max_hp))
		self.spell.convert_unit(self.owner, self.owner.max_hp + self.damage)

class Machination(Spell):
	def on_init(self):
		self.name = "Cold Machination"
		self.asset = ["TcrsCustomModpack", "Icons", "cold_machination"]
		self.tags = [Tags.Ice, Tags.Metallic, Tags.Sorcery, Tags.Conjuration]
		self.level = 3 ##Aiming for level 3 or 4. 3 Competes with lightning spire, and silver spear. 4 with fewer metallic spells. Maybe push this to 5?

		self.max_charges = 5
		self.damage = 30
		self.damage_type = [Tags.Ice]
		self.range = 8
		
		self.can_target_empty = False
		def WormBallRemainder():
			unit = WormBallIron(5)
			return unit
		def WormBallHuge():
			unit = WormBallIron(50)
			return unit
		self.units = [WormBallRemainder, DancingBlade, GlassMushboom, MetalMantis, Golem, Gargoyle, WormBallHuge, SpikeBall, IronFiend]
		
		##Some sort of anti-construct upgrade that adds a damage type that constructs don't resist? It's not designed to be good at killing constructs.
		self.upgrades['smith'] = (1, 5, "Blacksmith", "Also deals [Fire] damage.\nCast your Armageddon Blade on the first construct made from each cast of the spell.",[Tags.Fire])
		self.upgrades['garden'] = (1, 4, "Bizarrtificer", "Also deals [Arcane] damage.\nInstead of constructs, cast your psychic seedling on random tiles for each 10 hp the target had.",[Tags.Arcane])
		self.upgrades[('accumulation','duration')] = ([1,4], 5, "Accumulation", "Applies a debuff, which adds all damage taken by the target over [4:duration] turns to the max hp of the constructs summoned, if the target dies with the debuff.",[Tags.Enchantment])

	def get_description(self):
		return ("Deals [{damage}_ice:ice] to target unit. If it dies it spawns random constructs around it. "
				"The total hp of constructs is equal to the max hp of the unit.\n"
				"[Fire] targets summon twice as many constructs.").format(**self.fmt_dict())

	def cast_instant(self, x, y):
		u = self.caster.level.get_unit_at(x,y)
		if u == None:
			return
		if self.get_stat('accumulation'):
			duration = self.get_stat('duration',base=4)
			u.apply_buff(MachinationBuff(self), duration)
		u.deal_damage(self.get_stat('damage'), Tags.Ice, self)
		if self.get_stat('garden'):
			u.deal_damage(self.get_stat('damage'), Tags.Arcane, self)
		if self.get_stat('smith'):
			u.deal_damage(self.get_stat('damage'), Tags.Fire, self)
		if not u.is_alive() and not self.get_stat('accumulation'):
			self.convert_unit(u, u.max_hp)

	def convert_unit(self, unit, sum_damage):
		u = unit
		damage = sum_damage
		if Tags.Fire in u.tags:
			damage = damage * 2
			
		if self.get_stat('garden'):
			count = damage // 10
			tiles = [t for t in self.caster.level.iter_tiles() if t.is_floor()]
			for i in range(count): ##TODO check if this crashes when every single floor is occupied.
				spell = self.caster.get_or_make_spell(BrainSeedSpell)
				t = random.choice(tiles)
				self.caster.level.act_cast(self.caster, spell, t.x, t.y, False)
		else:
			first = True
			index = len(self.units) - 1
			while damage > 5: ##This must be higher than the lowest hp in the list to avoid infinite looping, in this case 5
				construct = self.units[index]()
				if damage > construct.max_hp:
					damage -= construct.max_hp
					self.summon(construct, Point(u.x,u.y), sort_dist=False)
					if self.get_stat('smith') and first:
						spell = self.caster.get_or_make_spell(ArmeggedonBlade)
						self.caster.level.act_cast(self.caster, spell, construct.x, construct.y, False)
					first = False
					index = random.randint(0, len(self.units)-1)
				else:
					if first:
						index = index - 1
					else:
						index = random.randint(0,index)
			if damage > 0:
				construct = WormBallIron(damage)
			self.summon(construct, Point(u.x,u.y), sort_dist=False)
			if self.get_stat('smith') and first:
				spell = self.caster.get_or_make_spell(ArmeggedonBlade)
				self.caster.level.act_cast(self.caster, spell, construct.x, construct.y, False)
				first = False


def SkullWorm():
	unit = Unit()
	unit.max_hp = 35
	unit.name = "Skullsnake"
	unit.asset = ["TcrsCustomModpack", "Units", "skullworm"]
	unit.tags = [Tags.Nature, Tags.Dark, Tags.Undead]

	unit.spells.append(SimpleMeleeAttack(12))

	unit.resists[Tags.Physical] = 50
	unit.resists[Tags.Dark] = 100
	unit.resists[Tags.Poison] = 100
	unit.resists[Tags.Ice] = -50

	unit.burrowing = True
	return unit

class Skullbuffery(Buff):
	def __init__(self, spell):
		self.spell = spell
		Buff.__init__(self)

	def on_init(self):
		self.color = Tags.Dark.color
		self.name = "Skulldiggery"
		#status.asset
		self.owner_triggers[EventOnDeath] = self.on_death

	def on_death(self, evt):
		unit = SkullWorm()
		unit.team = self.spell.caster.team
		apply_minion_bonuses(self.spell,unit)
		unit.turns_to_death = None
		self.spell.summon(unit, self.owner)
		if self.spell.get_stat('trickery'):
			unit.apply_buff(Skullbuffery(self.spell), self.spell.get_stat('duration',base=3)  + self.spell.get_stat('minion_duration', base=3))

class Skulldiggery(Spell):
	def on_init(self):
		self.name = "Skulldiggery"
		self.tags = [Tags.Dark, Tags.Nature, Tags.Enchantment, Tags.Conjuration]
		self.level = 2 ##Level 2-3? Well stated for lvl2 spell, but not the easiest spell to trigger. With 'lasting' it will cost 4-5 and be comparable to petrify + golem
		self.asset = ["TcrsCustomModpack", "Icons", "skulldiggery"] ##Fix the pixel at the joint that moves up and down, it's too thin

		self.max_charges = 10
		self.range = 10
		self.duration = 1
		
		example = SkullWorm()
		self.minion_health = example.max_hp
		self.minion_damage = example.spells[0].damage

		self.can_target_empty = False
		self.quick_cast = 1

		self.upgrades['betrayal'] = (1, 1, "Betrayal", "Also berserk the target for [1:duration] turn.",[Tags.Chaos])
		self.upgrades['lasting'] = (1, 2, "Dishonesty", "The buff now lasts for [10:duration] turns instead of 1.")
		self.upgrades[('trickery','minion_duration')] = ([1,5], 2, "Trickery", "The Skullsnake spawns with this buff for [1:duration] turns, scaling with duration, plus [5:minion_duration] scaling with minion duration.")
		
	def get_description(self):
		return ("Target unit gains Skulldiggery for [{duration}_turn:duration]. If it dies spawn a skullsnake at its location. "
				"If it was an ally, it also reincarnates.\nCasting this spell takes half of your turn.\n"
				"Skullsnakes are burrowing melee units with [{minion_health}_HP:minion_health] and deal [{minion_damage}_physical:physical] damage.").format(**self.fmt_dict())

	def get_extra_examine_tooltips(self):
		return [SkullWorm(), self.spell_upgrades[0], self.spell_upgrades[1], self.spell_upgrades[2]]

	def cast(self, x, y):
		unit = self.caster.level.get_unit_at(x, y)
		if self.get_stat('lasting'):
			duration = self.get_stat('duration', base=10)
		else:
			duration = 1
		if self.get_stat('betrayal'):
			unit.apply_buff(BerserkBuff(),1)
		unit.apply_buff(Skullbuffery(self),duration)
		if not are_hostile(self.caster, unit):
				unit.apply_buff(ReincarnationBuff(1),duration)
		yield



class EyedraDurable(Buff):
	def __init__(self, spell):
		self.spell = spell
		Buff.__init__(self)
		
	def on_init(self):
		self.count = 0
		
	def on_advance(self):
		self.count += 1
		if self.count == 3:
			p = Point(self.owner.x, self.owner.y)
			self.owner.kill(trigger_death_event=False)
			self.spell.owner.level.act_cast(self.spell.owner, self.spell, p.x, p.y, pay_costs=False)

class EyedraReincarnation(Buff):
	def __init__(self, heads, spell):
		self.heads = heads
		self.spell = spell
		Buff.__init__(self)

	def on_init(self):
		self.color = Tags.Dragon.color
		self.name = "Eyedra Heads"
		self.buff_type = BUFF_TYPE_PASSIVE
		self.owner_triggers[EventOnDeath] = self.on_death
		self.owner_triggers[EventOnBuffApply] = self.on_apply_buffs
		
	def on_apply_buffs(self, evt):
		if isinstance(evt.buff, ReincarnationBuff):
			self.owner.remove_buffs(ReincarnationBuff)

	def on_death(self, evt):
		if self.heads > 1:
			self.owner.level.queue_spell(self.make_eyedra(self.owner.x,self.owner.y))
		elif self.heads == 1 and self.spell.get_stat('durable'):
			unit = Eyedra(0)
			unit.spells.clear()
			self.spell.summon(unit, Point(self.owner.x,self.owner.y))
			unit.apply_buff(EyedraDurable(self.spell))
		if self.spell.get_stat('spawn_eyes'):
			caster = self.spell.owner
			spell = caster.get_or_make_spell(SummonFloatingEye)
			self.owner.level.act_cast(caster, spell, evt.unit.x, evt.unit.y, pay_costs=False)

	def make_eyedra(self, x, y):
		unit = Eyedra(self.heads-1)
		if self.spell.get_stat('draconic'):
			unit.spells[1].damage += self.spell.caster.get_mastery(Tags.Dragon) // 2
		self.spell.summon(unit, Point(x,y))
		unit.apply_buff(EyedraReincarnation(self.heads - 1, self.spell))
		yield

class EyedraGetTarget(Spell):
	def on_init(self):
		self.name = "Many Eyed Gaze"
		self.description = "Attacks up to 6 units, one for each eye, using the Eyedra's ranged attack."
		self.range = 99

	def cast(self, x, y):
		if self.caster.heads == 0:
			return
		possible_targets = self.caster.level.units
		possible_targets = [t for t in possible_targets if self.caster.level.are_hostile(t, self.caster)]
		possible_targets = [t for t in possible_targets if self.caster.level.can_see(t.x, t.y, self.caster.x, self.caster.y)]
		for s in self.caster.spells:
			if s.name == "Eye Bolt":
				eyebolt = s
		for i in range(self.caster.heads):
			if len(possible_targets) <= 0:
				break
			t = possible_targets.pop(0)
			self.caster.level.act_cast(self.caster, eyebolt, t.x, t.y, pay_costs=False)
		yield

def Eyedra(heads=1):
	unit = Unit()
	unit.max_hp = 20
	unit.name = "The Eyedra"
	unit.tags = [Tags.Arcane, Tags.Eye, Tags.Dragon]
	unit.heads = heads
	if unit.heads >= 0 or unit.heads <= 5:
		unit.asset = ['TcrsCustomModpack', 'Units', 'eyedra'+str(heads)]
	else:
		unit.asset = ['TcrsCustomModpack', 'Units', 'eyedra0']
	unit.stationary = True
	unit.spells.append(EyedraGetTarget())
	eyebolt = SimpleRangedAttack(damage=4, damage_type=Tags.Arcane, range=99)
	eyebolt.name = "Eye Bolt"
	unit.spells.append(eyebolt)
	return unit

class SummonEyedra(Spell):
	def on_init(self):
		self.name = "Release the Eyedra"
		self.tags = [Tags.Arcane, Tags.Dragon, Tags.Conjuration, Tags.Eye]
		self.level = 7 ##Tentative level 5 or 6, starts off whatever and scales very well. Can't be cast multiple times like other conjurations
		self.asset = ["TcrsCustomModpack", "Icons", "eyedra_icon"]

		self.max_charges = 2
		self.range = 5
		self.minion_health = 25
		self.minion_damage = 5
		
		self.stats.append('shot_cooldown')
		self.shot_cooldown = 3
		self.must_target_empty = True

		self.upgrades['spawn_eyes'] = (1, 1, "Independent Oversight", "Each time the Eyedra dies, it casts your floating eye.")
		self.upgrades['draconic'] = (1, 7, "Dragonic Lineage", "The Eyedra's gazing attack gains damage equal to half of your SP spent on [dragon] magic.")
		self.upgrades['durable'] = (1, 2, "Durable", "Instead of dying at 0 eye-heads, it becomes headless for 5 turns. If it survives, Summon Eyedra is recast at its location.")

	def get_description(self):
		return ("Summon the Eyedra, a stationary minion with 4 eye-heads. For each head it can attack one unit in line of sight for [{minion_damage}_arcane:arcane] damage. \n"
				"The Eyedra loses one head each time it dies, reviving on its tile. It gains 1 head for each 1 eye shot cooldown.\n"
				"You can only have one Eyedra, it cannot be given reincarnations, and casting it again moves it to the target tile and grants it a turn.").format(**self.fmt_dict())


	def cast_instant(self, x, y):
		unique_unit = [u for u in self.caster.level.units if not are_hostile(self.caster, u) and "The Eyedra" in u.name] ##If 1 is berserked, you can have 2, but I don't really care
		target = Point(x,y)
		heads = 4 + (3 - self.get_stat('shot_cooldown'))
		if heads > 6: #Update to higher numbers as I make bigger sprites?
			heads = 6
		if unique_unit == []:
			unit = Eyedra(heads)
			unit.buffs.append(EyedraReincarnation(unit.heads,self))
			#if self.get_stat('draconic'):
			#	for s in unit.spells:
			#		if s.name == "Eye Bolt":
			#			s.damage += self.get_stat('breath_damage', base=4)
			if self.get_stat('draconic'):
				unit.spells[1].damage += self.caster.get_mastery(Tags.Dragon) // 2
			apply_minion_bonuses(self, unit)
			self.summon(unit, target)
		else:
			self.caster.level.act_move(unique_unit[0], target.x, target.y, teleport=True)
			unique_unit[0].advance()



def QuicksilverGeist():
	geist = Ghost()
	geist.name = "Mercurial Geist"
	geist.asset_name = "mercurial_geist"
	geist.max_hp = 25
	geist.tags.append(Tags.Metallic)
	trample = SimpleMeleeAttack(12,trample=True)
	geist.spells.append(trample)
	return geist

class ShieldOrb(OrbSpell):
	def on_init(self):
		self.name = "Unbreakable Orb"
		self.tags = [Tags.Metallic, Tags.Orb, Tags.Conjuration]
		self.asset = ["TcrsCustomModpack", "Icons", "metal_orb"]
		self.level = 2 ##Attempting to produce a low level orb spell that's very low impact with many charges.
	
		self.max_charges = 20
		self.range = 12
		self.minion_health = 25
		self.minion_damage = 15
		
		self.upgrades['erupt'] = (1, 1, "Volcanic Heart", "If the orb ends over a chasm, you cast your Volcanic Eruption on said chasm.")
		self.upgrades['cleave'] = (1, 2, "Angelic Sword", "The orb gains the cleaving sword of your Call Seraph spell instead of a simple melee attack.",[Tags.Holy])
		self.upgrades['spear'] = (1, 5, "Argent Spear", "The orb has your silver spear on a 2 turn cooldown.",[Tags.Holy])
		self.upgrades[('orb_walk','num_summons')] = ([1,2], 1, "Quicksilver Coating", "Targeting an existing Unbreakable Orb destroys it, summoning [{num_summons}:num_summons] Quicksilver Geists from your mercurize spell.")

	def get_description(self):
		return ("Summons an Unbreakable Orb which attacks as it moves, dealing [{minion_damage}_physical:physical] damage to one unit in melee range.\n"
				"The orb has no will of its own, each turn it will float one tile towards the target.\n"
				"The orb is immune to all elements.").format(**self.fmt_dict())
	
	def on_orb_move(self, orb, next_point):
		pass

	def on_make_orb(self, orb):
		orb.name = "Unbreakable Orb"
		orb.asset =  ["TcrsCustomModpack", "Units", "shield_orb_axe"]
		orb.tags.append(Tags.Metallic)

		if self.get_stat('cleave'):
			melee = SeraphimSwordSwing()
			call = self.caster.get_or_make_spell(SummonSeraphim)
			if call.get_stat('moonblade'):
				melee.arcane = True
			else:
				melee.arcane = False
			melee.damage = call.get_stat('minion_damage')
			orb.spells.append(melee)
			orb.asset =  ["TcrsCustomModpack", "Units", "shield_orb_seraph"]
		elif self.get_stat('spear'):
			spear = grant_minion_spell(SilverSpearSpell, orb, self.caster, 2)
			orb.asset =  ["TcrsCustomModpack", "Units", "shield_orb_spear"]
			orb.spells.append(SimpleMeleeAttack(damage=self.get_stat('minion_damage'), damage_type=Tags.Physical))
		else:
			orb.spells.append(SimpleMeleeAttack(damage=self.get_stat('minion_damage'), damage_type=Tags.Physical))

	def on_orb_collide(self, orb, next_point):
		orb.level.show_effect(next_point.x, next_point.y, Tags.Physical)
		if self.get_stat('erupt') and self.owner.level.tiles[orb.x][orb.y].is_chasm: ##TODO replace this with a trampling melee attack that shoves things out of the way. More in character
			eruption = self.caster.get_or_make_spell(Volcano)
			self.caster.level.act_cast(self.caster, eruption, orb.x, orb.y, pay_costs=False)
		yield

	def on_orb_walk(self, existing):
		x = existing.x
		y = existing.y
		hp = existing.max_hp
		existing.kill()
		geist = QuicksilverGeist()
		spell = self.caster.get_or_make_spell(MercurizeSpell)
		for i in range(self.get_stat('num_summons')):
			geist = spell.get_geist()
			geist.max_hp = hp
			self.summon(geist, target=Point(x,y))
			if spell.get_stat('noxious_aura'):
				geist.apply_buff(DamageAuraBuff(damage=1, damage_type=Tags.Poison, radius=2))
			if spell.get_stat('vengeance'):
				geist.apply_buff(MercurialVengeance(spell))
		yield

	def get_extra_examine_tooltips(self):
		return [self.spell_upgrades[0], self.spell_upgrades[1], self.spell_upgrades[2], self.spell_upgrades[3], QuicksilverGeist()]



class FungalSpores(Upgrade):
	def on_init(self):
		self.level = 4
		self.name = "Fungal Spores"
		self.description = ("Whenever any unit dies within a poison cloud, cast your toxic spores spell at that location.")
		self.global_triggers[EventOnDeath] = self.on_death

	def on_death(self, evt):
		cloud = self.owner.level.tiles[evt.unit.x][evt.unit.y].cloud
		if cloud and (type(cloud) == PoisonCloud):
			mush_spell = self.owner.get_or_make_spell(ToxicSpore)
			self.owner.level.act_cast(self.owner, mush_spell, evt.unit.x, evt.unit.y, pay_costs=False)

class Gooify(Buff):
	def __init__(self, spell):
		self.spell = spell
		Buff.__init__(self)

	def on_init(self):
		self.color = Tags.Slime.color
		slime_spell = self.spell.owner.get_or_make_spell(SlimeformSpell)
		spawn_funcs = GreenSlime
		if slime_spell.get_stat('fire_slimes'):
			spawn_funcs = RedSlime
		if slime_spell.get_stat('ice_slimes'):
			spawn_funcs = IceSlime
		if slime_spell.get_stat('void_slimes'):
			spawn_funcs = VoidSlime
		if slime_spell.get_stat('electric_slimes'):
			spawn_funcs = ElectricSlime
		if slime_spell.get_stat('blood_slimes'):
			spawn_funcs = BloodSlime
		self.spawner = spawn_funcs
		self.name = "Gooify: " + self.spawner().name
		self.owner_triggers[EventOnDeath] = self.on_death
		
	def on_death(self, evt):
		slime_buff = SlimeformBuff(self.spell)
		slime_spell = self.spell.owner.get_or_make_spell(SlimeformSpell)
		unit = slime_buff.make_summon(self.spawner)
		slime_spell.summon(unit, target=Point(self.owner.x, self.owner.y))

class PoisonousGas(Spell): #Based on "Bleezy"'s idea of a spell with constant volume.
	def on_init(self):
		self.name = "Poisonous Gas"
		self.level = 3 ##Aiming for 3 as a poison spell stronger than toxin burst but also lets you combo with mushbooms
		self.tags = [Tags.Nature, Tags.Enchantment]
		self.asset = ["TcrsCustomModpack", "Icons", "poisonousgas"]

		self.max_charges = 5
		self.damage = 10
		self.damage_type = [Tags.Poison]
		self.range = 10
		self.radius = 25
		self.duration = 6

		self.upgrades['slime'] = (1, 4, "Gooify", "All non [slime] units in the initial cast area get the gooify debuff, spawning a slime when they die. Inherits slime form upgrades.",[Tags.Slime])
		self.upgrades['mercury'] = (1, 4, "Phenylmercury", "Each cloud gives your mercurize debuff to the first unit it damages for [6:duration] turns.",[Tags.Dark, Tags.Metallic])
		self.add_upgrade(FungalSpores())

	def get_description(self):
		return ("Creates poison clouds in a [{radius}_tile:radius] tile area for 6 turns. The area starts at the center tile, goes out in all directions, and is stopped by wall tiles.\n"
				"Poison clouds deal [{damage}_poison:poison] damage per turn to units, and poisons non-immune units for [{duration}_turns:duration] turns.").format(**self.fmt_dict())

	def make_cloud(self, caster):
		cloud = PoisonCloud(caster, 9)
		cloud.source = self
		cloud.spell = self
		cloud.buff_turns = self.get_stat('duration')
		if self.get_stat('mercury'):
			spell = self.caster.get_or_make_spell(MercurizeSpell)
			buff = MercurizeBuff(spell)
			cloud.buff = buff
		return cloud

	def cast(self, x, y):
		for t in self.get_impacted_tiles(x,y):
			cloud = self.make_cloud(self.caster)
			self.caster.level.add_obj(cloud, t.x, t.y)
			
			if self.get_stat('slime'):
				unit = self.caster.level.get_unit_at(t.x, t.y)
				if unit and Tags.Slime not in unit.tags:
					unit.apply_buff(Gooify(self))
		yield

	def get_impacted_tiles(self, x, y):
		tiles = []
		remaining = self.get_stat('radius')
		points_to_check = [Point(x,y)]
		for p in points_to_check:
			if p in tiles or remaining == 0 or not self.caster.level.is_point_in_bounds(p):
				pass
			elif not self.caster.level.tiles[p.x][p.y].is_wall():
				tiles.append(p)
				remaining -= 1
				points_to_check.append(Point(p.x+1,p.y))
				points_to_check.append(Point(p.x-1,p.y))
				points_to_check.append(Point(p.x,p.y+1))
				points_to_check.append(Point(p.x,p.y-1))
		return tiles



class HemortarBuff(Buff):
	def __init__(self, spell):
		Buff.__init__(self)
		self.spell = spell
		self.counter = 0
		self.counter_upgrade = 0

		self.owner_triggers[EventOnSpendHP] = self.on_spend_hp
		if self.spell.get_stat('ordnance'):
			self.global_triggers[EventOnDamaged] = self.on_damaged


	def on_init(self):
		self.name = "Hemoartillery"
		self.color = Tags.Blood.color
		self.buff_type = BUFF_TYPE_BLESS
		self.stack_type = STACK_REPLACE
		self.charges = 0
		self.description = "Blood Charges %d\n" % self.charges

	def on_spend_hp(self, evt):
		self.counter += evt.hp
		while self.counter >= 10:
			self.counter -= 10
			self.charges += 1

	def on_damaged(self, evt):
		if not evt.source:
			return
		if not evt.source.owner:
			return
		if not hasattr(evt.source, 'tags'):
			return
		if Tags.Blood in evt.source.tags and isinstance(evt.source, Spell):
			self.counter_upgrade += evt.damage
			while self.counter_upgrade >= 50:
				self.counter_upgrade -= 50
				self.charges += 1

	def on_advance(self):
		#print(self.charges)
		self.description = "Blood Charges %d\n" % self.charges
		if self.charges >= 1:
			self.charges -= 1
			self.description = "Blood Charges %d\n" % self.charges
			self.turns_left += 1
			if self.spell.get_stat('howitzer'):
				spell = self.owner.get_or_make_spell(SummonWolfSpell)
			else:
				all_spells = self.owner.spells
				spells = [s for s in all_spells if (Tags.Sorcery in s.tags) and (Tags.Translocation not in s.tags) and s.range > 1]
				if self.spell.get_stat('empower'):
					spells = [s for s in spells if (s.level == 2 or s.level == 3)]
				else:
					spells = [s for s in spells if s.level == 2]
				if spells == []:
					return
				spell = random.choice(spells)

			possible_targets = self.owner.level.units ##Note - line of sight works weirdly with cone spells, perhaps unsolveable
			possible_targets = [t for t in possible_targets if self.owner.level.are_hostile(t, self.owner)]
			possible_targets = [t for t in possible_targets if self.owner.level.can_see(t.x, t.y, self.owner.x, self.owner.y)] ##Check this line
			if possible_targets:
				random.shuffle(possible_targets)
				target = max(possible_targets, key=lambda t: distance(t, self.owner))
				#print(target.name)
				self.owner.level.act_cast(self.owner, spell, target.x, target.y, pay_costs=False)

class Hemortar(Spell):
	def on_init(self):
		self.name = "Hemocytic Artillery" # Hemortar?
		self.tags = [Tags.Sorcery, Tags.Enchantment, Tags.Blood]
		self.asset = ["TcrsCustomModpack", "Icons", "hemortar"]
		self.level = 4 ##On its own, this is a relatively strong esp with some lvl 3 spells. E.g. converts, 2 casts of goatia into chain lightning for example, that is a bit powerful. 
		##bloody ordnance is beyond too powerful. Level 4-5? This is actually pretty strong even with the current nerfs. To level 5 or  6.
		
		self.hp_cost = 10
		self.max_charges = 2
		self.range = 0
		self.duration = 5
		
		self.self_target = True

		self.upgrades['howitzer'] = (1, 4, "Howlitzer", "Instead of casting a sorcery, casts your wolf spell at the furthest target.", [Tags.Nature])
		self.upgrades['ordnance'] = (1, 7, "Bloody Ordnance", "Now also casts a spell for each 50 damage dealt by blood spells.")
		self.upgrades['empower'] = (1, 5, "The Great Bombard", "Can also cast level 3 sorceries.")
		self.upgrades['quick'] = (1, 2, "Quick-firing Gun", "Start off with 3 blood charges.")

	def get_description(self):
		return ("For [{duration}_turns:duration], for every 10 hp spent on [blood] spells, gain a blood charge. "
				"Each turn expend a charge to cast a level 2 [Sorcery] at the furthest enemy in line of sight. "
				"Extends by 1 turn each time you expend a blood charge.\n"
				"Won't cast [Translocation] spells, or spells with range less than 2.").format(**self.fmt_dict())

	def cast(self, x, y):
		buff = HemortarBuff(self)
		if self.get_stat('quick'):
			buff.charges = 3
		self.caster.apply_buff(buff, self.get_stat('duration'))
		yield



class IcyBeastCurse(Buff):
	def __init__(self, spell):
		self.spell = spell
		Buff.__init__(self)

	def on_init(self):
		self.buff_type = BUFF_TYPE_CURSE
		self.stack_type = STACK_NONE
		self.name = "Curse of the Beast"
		self.color = Tags.Dark.color
		self.duration = 3
		self.count = 3
		self.global_triggers[EventOnDeath] = self.on_death

	def on_death(self, evt):
		if not are_hostile(evt.unit, self.owner):
			return
		if not evt.damage_event:
			return
		if evt.damage_event.source.owner == self.owner:
			if self.spell.get_stat('hunger'):
				if self.count <= 0:
					self.owner.apply_buff(RegenBuff(50))
				self.count = 3
			else:
				self.owner.apply_buff(FrozenBuff(),3)
			
	def on_advance(self):
		self.count -= 1
		#print(self.count)
		if self.count <= 0:
			if self.spell.get_stat('hunger'):
				self.owner.remove_buffs(RegenBuff)
				self.owner.deal_damage(15, Tags.Holy, self)

def IcyBeast():
	unit = Unit()
	unit.name = "Ice-cursed Beast"
	unit.tags = [Tags.Fire, Tags.Ice, Tags.Demon]
	unit.asset = ["TcrsCustomModpack", "Units", "cursed_beast"]

	unit.max_hp =  250
	fangs = SimpleMeleeAttack(damage=30,damage_type=Tags.Dark,drain=True)
	fangs.name = "Draining Fangs"
	unit.spells.append(fangs)
	leap = LeapAttack(damage=15,range=6,damage_type=Tags.Ice)
	leap.name = "Icy Leap"
	unit.spells.append(leap)
	
	unit.buffs.append(RegenBuff(15))
	unit.resists[Tags.Fire] = 100
	unit.resists[Tags.Dark] = 100
	unit.resists[Tags.Poison] = 100
	unit.resists[Tags.Holy] = -100
	unit.resists[Tags.Ice] = -100
	return unit

class SummonIcyBeast(Spell):
	def on_init(self):
		self.name = "Ice-Cursed Beast"
		self.tags = [Tags.Ice, Tags.Dark, Tags.Conjuration]
		self.level = 6 ##Intended to be nigh-unkillable extraordinarily slow as it freezes itself, Level6?
		self.asset = ["TcrsCustomModpack", "Icons", "cursed_beast"]

		self.max_charges = 1
		self.range = 5
		self.minion_health = 250
		self.minion_damage = 30
		self.minion_range = 6
		
		self.upgrades['exsanguinate'] = (1, 3, "Bloodstarved Beast", "The Beast gains your exsanguinate spell on an 8 turn cooldown.", [Tags.Blood])
		self.upgrades[('unchained','minion_duration')] = ([1,25], 4, "Unchained", "The Beast no longer freezes, but it only lasts [25:minion_duration] turns.")
		self.upgrades['hunger'] = (1, 4, "Endless Hunger", "The Beast no longer freezes, but it takes 15 holy damage each turn and has no regeneration if 3 turns pass without it killing.")

	def get_description(self):
		return ("Summons a frozen Ice-Cursed Beast, who thaws in 3 turns. Each time it kills a unit it refreezes. \n"
				"The Beast has [{minion_health}_HP:minion_health], a [{minion_damage}_dark:dark] damage lifestealing melee attack, and a [{minion_range}_tile:minion_range] icy leaping attack."
				"The beast heals 15 hp every turn.").format(**self.fmt_dict())
	
	def get_extra_examine_tooltips(self):
		return [IcyBeast()] + self.spell_upgrades
	
	def cast(self, x, y):
		unit = IcyBeast()
		apply_minion_bonuses(self, unit)
		self.summon(unit,Point(x,y))
		if self.get_stat('exsanguinate'):
			grant_minion_spell(Exsanguinate, unit, self.caster, 8, True)
		if self.get_stat('hunger'):
			unit.apply_buff(IcyBeastCurse(self))
		elif self.get_stat('unchained'):
			unit.turns_to_death = self.get_stat('minion_duration', base=25)
		else:
			unit.apply_buff(FrozenBuff(),3)
			unit.apply_buff(IcyBeastCurse(self))
		yield



class CloudWalkBuff(Buff):
	def __init__(self, spell):
		self.spell = spell
		Buff.__init__(self)
	def on_init(self):
		self.buff_type = BUFF_TYPE_BLESS
		self.stack_type = STACK_TYPE_TRANSFORM
		self.name = "Cloudwalking"
		self.transform_asset = ["TcrsCustomModpack", "Units", "player_cloud_form"]
		self.color = Tags.Translocation.color
		self.resists[Tags.Lightning] = 100
		self.resists[Tags.Ice] = 100

	def on_advance(self):
		self.owner.moves_left = 0

	def on_unapplied(self):
		self.owner.moves_left = 0

	def on_pre_advance(self):
		c = self.owner.level.tiles[self.owner.x][self.owner.y].cloud
		if c == None:
			return
		clouds = self.spell.clouds
		if self.spell.get_stat('strange'):
			clouds.extend(PoisonCloud, FireCloud, Sandstorm)
		
		if type(c) in clouds:
			self.turns_left += 1
			c.kill()
			self.owner.moves_left = 2
			if not self.spell.get_stat('distance'):
				return
			
		pct = self.owner.tag_bonuses_pct[Tags.Translocation].get('range', 0) + self.owner.global_bonuses_pct.get('range', 0)
		value = (3 * ((100.0 +  pct) / 100.0)) + self.owner.tag_bonuses[Tags.Translocation].get('range', 0) + self.owner.global_bonuses.get('range', 0)
		value = int(math.ceil(value))
		print(value)
		self.owner.moves_left = value

class Cloudwalk(Spell):
	def on_init(self):
		self.name = "Cloudwalk"
		self.tags = [Tags.Ice, Tags.Lightning, Tags.Enchantment, Tags.Translocation]
		self.level = 3 ##Redesigned with my super cool quickmove thing
		self.asset = ["TcrsCustomModpack", "Icons", "cloud_walk"]
		
		self.duration = 1
		self.max_charges = 4
		self.range = 6
		
		self.must_target_empty = True
		self.clouds = [BlizzardCloud, StormCloud, RainCloud]

		self.upgrades['woe'] = (1, 3, "Woeful Passage", "Cast your woeful strike on the tile you teleported from.", [Tags.Dark])
		self.upgrades['distance'] = (1, 3, "Altostratus", "The number of bonus tiles you can move increases with any of your bonuses to [translocation] spell range.")
		self.upgrades['strange'] = (1, 1, "Strange Weather", "Can now target: Sandstorms, and Poison clouds", [Tags.Nature])

	def get_description(self):
		return ("Teleport to a tile which has a Blizzard, Thundercloud, or Rain cloud on it, then gain cloudwalker for 1 turn.\n"
				"Cloudwalker grants you 100 [ice] and [lightning] resist, and 3 bonus tiles of movement each turn, if you start your turn in a cloud.\n"
				"Cloudwalker consumes the cloud to gain 1 duration.").format(**self.fmt_dict())

	def can_cast(self, x, y): ##TODO Absolute 9000 IQ idea, see if quickcast can be set here so it applies while a spell is being cast.
		if self.get_stat('requires_los'):
			if not self.caster.level.can_see(self.caster.x, self.caster.y, x, y, light_walls=self.cast_on_walls):
				return False
		cloud = self.caster.level.tiles[x][y].cloud
		if type(cloud) in self.clouds:
			cloud = True
		return Spell.can_cast(self, x, y) and self.caster.level.can_move(self.caster, x, y, teleport=True) and cloud

	def get_targetable_tiles(self):
		x = self.caster.x
		y = self.caster.y
		eligible_p = []
		points = self.caster.level.iter_tiles()
		if self.get_stat('strange'):
			self.clouds = [BlizzardCloud, StormCloud, PoisonCloud, FireCloud, Sandstorm]
		for p in points:
			if not self.can_cast(p.x, p.y):
				continue
			cloud = self.caster.level.tiles[p.x][p.y].cloud
			if cloud and (type(cloud), Cloud):
				eligible_p.append(p)
		return eligible_p

	def cast(self, x, y):
		origin = Point(self.caster.x, self.caster.y)
		self.caster.level.act_move(self.caster, x, y, teleport=True)
		self.caster.level.show_effect(origin.x, origin.y, Tags.Translocation, minor=True)
		self.caster.apply_buff(CloudWalkBuff(self), 2)
		if self.get_stat('woe'):
			spell = self.caster.get_or_make_spell(TridentOfWoe)
			self.caster.level.act_cast(self.caster, spell, origin.x, origin.y, pay_costs=False)
		yield



class RainbowSealBuff(Buff):
	def __init__(self, spell):
		self.spell = spell
		Buff.__init__(self)
		self.tags = []

	def on_init(self):
		self.name = "Rainbow Seal"
		self.stack_type = STACK_REPLACE
		self.buff_type = BUFF_TYPE_BLESS
		self.dtypes = [Tags.Fire, Tags.Ice, Tags.Lightning, Tags.Arcane, Tags.Dark, Tags.Physical, Tags.Poison, Tags.Holy]
		#self.global_triggers[EventOnDamaged] = self.on_damage
		#self.global_triggers[EventOnBuffApply] #Something that counts status effect enemies dying is cool ##TOdo symbol of torment that spreads statuses based on statuses?
		self.owner_triggers[EventOnSpellCast] = self.on_cast

	def get_description(self):
		num_tags = len(self.tags)
		return "Store each tag in any spell you cast.\nOn expiration, deals 3 damage of a random type, times the number of tags, to each enemy.\n\nCurrent tags: %d" % num_tags

	def on_cast(self, evt):
		for tag in evt.spell.tags:
			if tag not in self.tags:
				self.tags.append(tag)

	def on_unapplied(self):
		self.owner.level.queue_spell(self.rainbow())

	def rainbow(self):
		damage = len(self.tags) * 3
		enchdmg = self.owner.tag_bonuses[Tags.Enchantment].get('damage', 0) + self.owner.global_bonuses.get('damage', 0)
		if self.spell.get_stat('scaling'):
			flatdmg = enchdmg
		else:
			flatdmg = math.floor(enchdmg / 3)
		enchdmg_pct = self.owner.tag_bonuses_pct[Tags.Enchantment].get('damage', 0) ##There's no % increase to global damage, yet.
		enchdmg_pct = 1 + (enchdmg_pct/100)
		damage += flatdmg
		if enchdmg_pct != 0:
			damage *= enchdmg_pct
		#print(flatdmg)
		#print(enchdmg_pct)
		
		enemies = [u for u in self.owner.level.units if are_hostile(self.owner, u)]
		count = 1
		if self.spell.get_stat('double'):
			count = 2
		for u in enemies:
			for i in range(count):
				dtype = random.choice(self.dtypes)
				if u.resists[dtype] >= 100 and self.spell.get_stat('reroll'):
					dtype = random.choice(self.dtypes)
				u.deal_damage(damage, dtype, self.spell)
			yield

class RainbowSeal(Spell): ##Alternatives Crystal Wrath -> Arcane Ice Holy Lightning ##Tormenting Seal -> Arcane Ice Poison
	def on_init(self):
		self.name = "Rainbow Seal"
		self.tags = [Tags.Enchantment]
		self.level = 4 ##Level 4 seems reasonable. It's searing seal but it scales far worse but hits wider. needs upgrades, probably good at triggering stuff.
		self.asset = ["TcrsCustomModpack", "Icons", "rainbow_seal"] #Variant of Searing Seal

		self.max_charges = 6
		self.duration = 6
		self.damage = 3
		self.range = 0
		
		self.self_target = True
		
		self.upgrades['scaling'] = (1, 3, "Empowered", "Now scales with its flat damage with 100% efficiency.")
		self.upgrades['double'] = (1, 3, "Double Dip", "Deals damage a second time after the first, with a new random damage type.")
		self.upgrades['reroll'] = (1, 1, "Reroll", "If the unit is immune to the random damage, randomly select one more time.")

	def get_description(self):
		return ("Gain Rainbow Seal for [{duration}_turns:duration].\n"
				"When you cast a spell, the seal gains a charge for each unique tag in the spell, e.g. [Fire], [Sorcery], [Chaos], etc.\n"
				"When the seal expires, each enemy takes 3 damage multiplied by the number of charges, of a random type. Flat damage increases apply at 1/3rd of their effectiveness.\n"
				"Recasting the spell will expire the current seal and create a new one.").format(**self.fmt_dict())

	def cast_instant(self, x, y):
		self.caster.apply_buff(RainbowSealBuff(self), self.get_stat('duration'))



class ShrapnelBreath(BreathWeapon):
	def on_init(self):
		self.name = "Shrapnel Breath"
		self.damage_type = Tags.Physical

	def get_description(self):
		return "Breathes a cone of shrapnel dealing %d [physical] damage" % self.damage

	def per_square_effect(self, x, y):
		self.caster.level.deal_damage(x, y, self.damage, self.damage_type, self)

class SteelFangsBuff(Buff):
	def __init__(self, spell):
		Buff.__init__(self)
		self.spell = spell
		self.hp_bonus = self.spell.get_stat('minion_health')
		self.damage = self.spell.get_stat('damage')
		self.breath_damage = self.spell.get_stat('minion_damage')

	def on_init(self):
		self.name = "Steel Fangs"
		self.stack_type = STACK_INTENSITY
		self.buff_type = BUFF_TYPE_BLESS
		self.color = Tags.Dragon.color

	def on_applied(self, owner):
		owner.cur_hp += self.hp_bonus
		owner.max_hp += self.hp_bonus
		for spell in self.owner.spells:
			if not hasattr(spell, 'damage'):
				continue
			if isinstance(spell, BreathWeapon):
				spell.damage += self.breath_damage
			else:
				spell.damage += self.damage

class SteelFangs(Spell):
	def on_init(self):
		self.name = "Steel Fangs"
		self.level = 3 ##Tentative 4, but dragon roar is just way stronger overall, affects the whole map, etc. Making it last forever as a compromise.
		self.asset = ["TcrsCustomModpack", "Icons", "steelfangs"] ##Variation of Drakentooth
		self.tags = [Tags.Enchantment, Tags.Dragon, Tags.Metallic]
		
		self.max_charges = 8
		self.range = 15
		self.damage = 5
		self.minion_damage = 10
		self.minion_health = 10
		
		self.can_target_empty = False
		self.unit_tags = [Tags.Dragon, Tags.Metallic]

		self.upgrades['breath'] = (1, 4, "Heart of the Drake", "Gives [Metallic] units a breath attack that deals [10:minion_damage] physical damage.")
		self.upgrades[('soul','shields')] = ([1,5], 2, "Steel Thy Soul", "Non [Arcane] units gain the [arcane] tag and [5:shields] shields.", [Tags.Arcane])
		self.upgrades['steal'] = (1, 3, "Stealing Fangs", "Steal [5:minion_damage] max hp from each non [Undead] adjacent unit and give it to the target.", [Tags.Dark])
		
	def get_description(self):
		return ("Target minion gains [{minion_damage}_bonus_damage:minion_damage] to their breath spells, "
				"and its other spells gain [{damage}_bonus_damage:damage].\n"
				"These bonuses scale with this spell's minion damage, and damage stat respectively.\n"
				"Target minion then gains the [metallic] and [dragon] tags, and [{minion_health}_max_hp:minion_health].\n"
				"The hp bonus scales with this spell's minion health stat.").format(**self.fmt_dict())

	def cast(self, x, y):
		unit = self.caster.level.get_unit_at(x, y)
		if unit:
			buff = SteelFangsBuff(self)
			if Tags.Metallic not in unit.tags:
				BossSpawns.apply_modifier(BossSpawns.Metallic, unit)
			else:
				if self.get_stat('breath'):
					breath_weapon = False
					for spell in unit.spells:
						s_type = type(spell)
						if (s_type == BreathWeapon):
							breath_weapon = True
					if not breath_weapon:
						breath = ShrapnelBreath()
						breath.damage = self.get_stat('minion_damage')
						unit.add_spell(breath)
			if not Tags.Dragon in unit.tags:
				unit.tags.append(Tags.Dragon)
			if not Tags.Arcane in unit.tags and self.get_stat('soul'):
				unit.tags.append(Tags.Arcane)
				unit.shields += self.get_stat('shields')
			unit.apply_buff(buff)
			if self.get_stat('steal'):
				for p in self.caster.level.get_adjacent_points(unit, filter_walkable=False):
					adj_unit = self.caster.level.get_unit_at(p.x, p.y)
					if adj_unit == None:
						pass
					elif adj_unit == self.caster or adj_unit == unit or Tags.Undead in adj_unit.tags:
						pass
					else:
						if adj_unit.max_hp < 10:
							hp = adj_unit.max_hp
						else:
							hp = 10
						print(hp)
						drain_max_hp(adj_unit, hp)
						unit.max_hp += hp
		yield



class Leapfrog(Spell):
	def on_init(self):
		self.name = "Leapfrog"
		self.level = 3 #Level 2 perhaps? Extremely specific in how it works, like aether swap, but limited in how it targets. Actually very strong in practice, level 3
		self.tags = [Tags.Nature, Tags.Translocation]
		self.asset = ["TcrsCustomModpack", "Icons", "leapfrog"]
		self.description = "Teleport to the opposite side of a unit, maintaining relative distance. Destination tile must be empty."
		
		self.max_charges = 15
		self.range = 16

		self.upgrades['quick_cast'] = (1, 3, "Quickcast", "Casting Leapfrog does not end your turn. Consumes 1 extra charge each cast.")
		self.upgrades['wolf'] = (1, 1, "Leapdog", "Cast your wolf at the spot you jumped from. Consumes 1 extra charge each cast.", [Tags.Conjuration])
		self.upgrades['walls'] = (1, 3, "Parkour", "Can now be cast on, or across walls.")
		
	def get_end_tile(self, x, y):
		newX = self.caster.x + (x - self.caster.x) * 2
		newY = self.caster.y + (y - self.caster.y) * 2
		newPoint = Point(newX, newY)
		if self.caster.level.is_point_in_bounds(newPoint):
			return newPoint
		else:
			return None

	def get_impacted_tiles(self, x, y):
		tile = self.get_end_tile(x, y)
		if tile != None:
			return [tile]
		else:
			return [Point(self.caster.x, self.caster.y)]

	def can_cast(self, x, y): ##Sees to work in all edge cases
		point = self.get_end_tile(x, y)
		if point == None:
			return False
		tile = self.caster.level.tiles[point.x][point.y]
		if tile == None:
			return False
		if tile.is_chasm and not self.caster.flying:
			return False
		if tile.is_wall() and not self.caster.burrowing:
			return False
		if self.caster.level.get_unit_at(point.x, point.y):
			return False
		u = self.caster.level.get_unit_at(x, y)
		if u == self.caster:
			return False
		if u != None:
			return True
		if self.get_stat('walls') and self.caster.level.tiles[x][y].is_wall():
			return True
		if not self.caster.level.can_see(self.caster.x, self.caster.y, x, y, light_walls=True):
			return False
		else:
			return False

	def cast(self, x, y):
		if self.get_stat('quick_cast'):
			self.cur_charges -= 1
		origin = Point(self.caster.x, self.caster.y)
		tile = self.get_end_tile(x, y)
		if self.caster.level.can_move(self.caster, tile.x, tile.y, teleport=True):
			self.caster.level.act_move(self.caster, tile.x, tile.y, teleport=True)
			if self.get_stat('wolf'):
				self.cur_charges -= 1
				spell = self.caster.get_or_make_spell(SummonWolfSpell)
				self.caster.level.act_cast(self.caster, spell, origin.x, origin.y, pay_costs=False)
		yield



class ChainJump(Upgrade): ##TODO implement on a different skill. Conceptually interesting to gain quickcast midway through, but has problems with how quickcast works
	def on_init(self):
		self.name = "Chaining Jump"
		self.level = 2
		self.owner_triggers[EventOnSpellCast] = self.on_spell_cast
		self.description = "Gain quickcast if this spell targets and kills a unit."
		self.spell = None

	def on_spell_cast(self, evt):
		if evt.spell.name == "Cavalier's Warp": 
			u = self.owner.level.get_unit_at(evt.x, evt.y)
			if u != None:
				dmg = evt.spell.get_stat('damage')
				dmg = dmg * (100 - u.resists[Tags.Holy]) / 100
				#print(dmg)
				if dmg >= u.cur_hp and u.shields == 0:
					evt.spell.quick_cast = 1
					self.spell = evt.spell
			else:
				evt.spell.quick_cast = 0
				self.spell = None
	
	def on_advance(self):
		if self.spell == None:
			return
		

	def remove_quickcast(self):
		self.spell.quick_cast = 0
		self.spell = None
		yield

class KnightlyLeap(Spell):
	def on_init(self):
		self.name = "Cavalier's Warp"
		self.level = 2
		self.tags = [Tags.Holy, Tags.Translocation] ##This is weird but not impossible to combine with cantrip cascade, for now it's not a sorcery
		self.asset = ["TcrsCustomModpack", "Icons", "knightlyleap"]

		self.max_charges = 15
		self.damage = 7
		self.damage_type = [Tags.Holy]
		self.range = 3
		
		self.quick_cast = True
		self.requires_los = False
		self.prev_loc = None
		self.must_target_empty = True

		self.upgrades['charger'] = (1, 2, "Gung Ho!", "If there are 3 or more adjacent enemies, cast your holy armor spell, and refresh your quick cast if you haven't already used it.")  
		self.upgrades['shields'] = (1, 2, "Knight's Shield", "Gain [1:shield] shield for each adjacent unit, up to 5 shields.")
		self.upgrades['mole'] = (1, 5, "Burrowing Jump", "Can target walls, melting them if necessary. (It is possible to trap yourself)")
		
	def get_description(self):
		return ("Teleport to target empty exactly 3 tiles away in an L-shape.\n"
				"Deal [{damage}_holy:holy] damage to all units adjacent to the tile.").format(**self.fmt_dict())

	def check_point(self, p):
		if not self.caster.level.is_point_in_bounds(p):
			return False
		if self.caster.level.get_unit_at(p.x, p.y) != None:
			return False
		if self.caster.level.tiles[p.x][p.y].is_chasm and not self.caster.flying:
			return False
		if self.caster.level.tiles[p.x][p.y].is_wall() and not (self.get_stat('mole') or self.caster.burrowing):
			return False
		return p

	def get_targetable_tiles(self):
		# cur_loc = Point(self.caster.x, self.caster.y) ##Implement this later.
		# if cur_loc == self.prev_loc:
		# 	return
		tiles = []
		x = self.caster.x
		y = self.caster.y
		x_mod = -2
		y_mod = -1
		for i in range(4):
			p = Point(x+x_mod,y+y_mod)
			if self.check_point(p) == p:
				tiles.append(p)
			p = Point(x+x_mod,y-y_mod)
			if self.check_point(p) == p:
				tiles.append(p)
			x_mod *= -1
			y_mod *= -1
			if i == 1:
				x_mod = -1
				y_mod = -2
		return tiles

	def can_cast(self, x, y):
		return Spell.can_cast(self, x, y) and (Point(x,y) in self.get_targetable_tiles())

	def cast(self, x, y):
		self.caster.level.show_effect(self.caster.x, self.caster.y, Tags.Translocation)
		if self.caster.level.tiles[x][y].is_wall() and self.get_stat('mole'):
			self.caster.level.make_floor(x, y)
		if self.caster.level.can_move(self.caster, x, y, teleport=True):
			self.caster.level.act_move(self.caster, x, y, teleport=True)
		count_adj = 0
		for t in self.caster.level.get_adjacent_points(self.caster, filter_walkable=False):
			if t.x == self.caster.x and t.y == self.caster.y:
				continue
			u = self.caster.level.get_unit_at(t.x, t.y)
			if u != None:
				if self.get_stat('shields') and self.caster.shields <= 5:
					self.caster.shields += self.get_stat('shields')
					if self.caster.shields > 5:
						self.caster.shields = 5
				if self.get_stat('charger') and are_hostile(u, self.caster):
					count_adj += 1
			self.caster.level.deal_damage(t.x, t.y, self.get_stat('damage'), Tags.Holy, self)
		if count_adj >= 3:
			spell = self.caster.get_or_make_spell(HolyShieldSpell)
			self.caster.level.act_cast(self.caster, spell, self.caster.x, self.caster.y, pay_costs=False)
			self.caster.quick_cast_used = False
		yield



class ChaosBeastBuff(Buff):
	def __init__(self, spell):
		Buff.__init__(self)
		self.spell = spell
		
	def on_init(self):
		self.name = "Snakeball"
		self.stack_type = STACK_NONE
		self.buff_type = BUFF_TYPE_PASSIVE
		self.color = Tags.Chaos.color
		self.owner_triggers[EventOnDamaged] = self.on_dmg
		self.owner_triggers[EventOnDeath] = self.on_death
		
	def on_dmg(self, evt):
		if Tags.Fire == evt.damage_type or Tags.Lightning == evt.damage_type or Tags.Physical == evt.damage_type:
			self.owner.max_hp += evt.damage

	def on_death(self, evt):
		hp = self.owner.max_hp
		if self.spell != None and self.spell.get_stat('yharnum'):
			self.owner.level.queue_spell(self.spawn_big(hp))
		else:
			self.owner.level.queue_spell(self.spawn(hp))

	def spawn(self, hp):
		num = hp // 9
		for i in range(num):
			unit = random.choice([Snake(), FireSnake(), GoldenSnake()])
			if self.owner.source:
				unit.source = self.owner.source
				apply_minion_bonuses(self.owner.source, unit)
			if self.spell != None:
				unit.turns_to_death = self.spell.get_stat('minion_duration')
			self.summon(unit)
			yield
			
	def spawn_big(self, hp):
		num = hp // 36
		for i in range(num):
			unit = random.choice( [StarfireSnakeGiant(), ChaosSnakeGiant(), SnakeGiant()] )
			if unit.name == "Giant Chaos Snake":
				unit.name = "Giant Lightning Snake"
			if self.owner.source:
				unit.source = self.owner.source
				apply_minion_bonuses(self.owner.source, unit)
			if self.spell != None:
				unit.turns_to_death = self.spell.get_stat('minion_duration') * 4
			
			self.summon(unit)
			yield

def ChaosBeast(s=None):
	unit = Unit()
	unit.asset = ["TcrsCustomModpack", "Units", "chaoticsnakeball"]
	unit.name = "Chaotic Snakeball"
	unit.max_hp = 36
	unit.spells.append(SimpleMeleeAttack(8, buff=Poison, buff_duration=10))
	unit.tags = [Tags.Chaos, Tags.Fire, Tags.Lightning, Tags.Living]
	unit.buffs.append(ChaosBeastBuff(s))
	return unit

class SummonChaosBeast(Spell):
	def on_init(self):
		self.name = "Chaotic Snakeball"
		self.tags = [Tags.Conjuration, Tags.Chaos]
		self.level = 3 ##Aiming for level 3, but the scaling on spawning snakes is quite strong, making them timed will help. The regular minion is reasonable.
		##Honestly so weird to scale these tags it can probably get more charges or something. None of these scale at all.
		self.asset = ["TcrsCustomModpack", "Icons", "chaotic_snake_icon"]

		self.max_charges = 3
		self.range = 5
		self.minion_health = 36
		self.minion_damage = 8
		self.minion_duration = 8

		self.upgrades['storm'] = (1, 4, "Storm Beast", "Gains 5 max hp when it witnesses a Lightning or Ice spell.", [Tags.Lightning, Tags.Ice])
		self.upgrades['slazephan'] = (1, 6, "Scholar of Scales", "If you do not have an allied Slazephan, summon Slazephan beside the wizard.", [Tags.Dragon])
		self.upgrades['yharnum'] = (1, 4, "Yharnanmite Monster", "Instead of small snakes, summon giant snakes for each 36 max hp, with 4 times as much life and duration.")

	def get_description(self):
		return ("Summons a Chaotic Snakeball, which gains max hp when it takes: [Physical], [Fire], or [Lightning] damage, equal to the damage taken.\n"
				"The Snakeball has [{minion_health}_HP:minion_health] and deals [{minion_damage}_damage:minion_damage] with its melee attack.\n"
				"On death it summons 1 snake for each 9 max hp it had. These snakes last [{minion_duration}_turns:minion_duration] turns.").format(**self.fmt_dict())
	
	def get_extra_examine_tooltips(self):
		giant_l_snake = ChaosSnakeGiant()
		giant_l_snake.name = "Giant Lightning Snake"
		return [ChaosBeast(), Snake(), FireSnake(), GoldenSnake(), self.spell_upgrades[0], self.spell_upgrades[1], SerpentPhilosopher(), self.spell_upgrades[2], SnakeGiant(), StarfireSnakeGiant(), giant_l_snake]

	def cast(self, x, y):
		unit = ChaosBeast(self)
		if self.get_stat('storm'):
			unit.apply_buff(SpiritBuff(Tags.Lightning))
			unit.apply_buff(SpiritBuff(Tags.Ice))
		apply_minion_bonuses(self, unit)
		unit.turns_to_death = None
		self.summon(unit, Point(x,y))
		if self.get_stat('slazephan'):
			snakes = [u for u in self.caster.level.units if not are_hostile(self.caster, u) and u.name == "Slazephan the Philosopher"]
			if snakes == []:
				snake = SerpentPhilosopher()
				philosophize = SnakePhilosophy_Advanced()
				snake.spells[1] = philosophize
				apply_minion_bonuses(self, snake)
				snake.turns_to_death = None
				self.summon(snake, Point(self.caster.x, self.caster.y))
		yield

class SnakePhilosophy_Advanced(SnakePhilosophy):
	def on_init(self):
		self.range = 99
		self.cool_down = 5
		self.name = "Advanced Snake Theory"
		self.description = "Transform a snake into a dragon."
		self.snakes = ["Snake", "Lightning Snake", "Fire Snake", "Death Snake", "Two Headed Snake", "Giant Snake", "Giant Chaos Snake", "Giant Fire Snake", "Giant Death Snake"]
		
	def can_cast(self, x, y):
		unit = self.caster.level.get_unit_at(x, y)
		return unit and unit.name in self.snakes and Spell.can_cast(self, x, y)
	
	def get_ai_target(self):
		candidates = [u for u in self.caster.level.get_units_in_los(self.caster) if u.name in self.snakes]
		candidates = [c for c in candidates if self.can_cast(c.x, c.y)]

		if candidates:
			return random.choice(candidates)



class CowardlyBuff(Buff):
	def __init__(self, spell):
		Buff.__init__(self)
		self.spell = spell

	def on_init(self):
		self.name = "Coward"
		self.stack_type = STACK_REPLACE
		self.buff_type = BUFF_TYPE_NONE
		self.color = Tags.Dark.color
		
	def on_advance(self):
		units = [u for u in self.owner.level.get_units_in_ball(self.owner, 3) if are_hostile(self.owner, u) and (Tags.Dark in u.tags or Tags.Undead in u.tags or u.name == "Wizard")]
		if units == []:
			return
		scared = False
		wizard = False
		for u in units:
			if u.name == "Wizard":
				wizard = True
				break
			elif Tags.Dark in u.tags or Tags.Undead in u.tags:
				scared = True
		if scared and not wizard:
			self.owner.apply_buff(FearBuff(), 2)

def CowardlyLion():
	unit = Unit()
	unit.name = "Cowardly Lion"
	unit.asset = ["TcrsCustomModpack", "Units", "cowardly_lion"] ##One single pixel on the back leg is red instead of yellow
	unit.max_hp = 100
	unit.spells.append(SimpleMeleeAttack(19))
	unit.tags = [Tags.Living]
	unit.resists[Tags.Physical] = 50
	unit.resists[Tags.Holy] = 50
	unit.resists[Tags.Dark] = -100
	return unit

class BeckonCowardlyLion(Spell):
	def on_init(self):
		self.name = "Cowardly Lion"
		self.tags = [Tags.Nature, Tags.Conjuration]
		self.level = 4 ##Immediately comparable to bear. Might be a level 4 and give it more charges with similar damage? Bear does attack twice. Cooler upgrades.
		self.asset = ["TcrsCustomModpack", "Icons", "cowardly_lion_icon"]

		self.max_charges = 3
		self.range = 5
		self.minion_health = 100
		self.minion_damage = 19
		
		self.must_target_walkable = True

		self.upgrades['pride'] = (1, 5, "Pride", "Your Lion becomes [fire], [ice], or [arcane] and can summon a corresponding lion on a 10 turn cooldown.")
		self.upgrades['roar'] = (1, 5, "Dreadful Roar", "Your Lion becomes [dark] gains your wave of dread spell on a 10 turn cooldown.", [Tags.Dark]) ##TODO make afraid of holy?
		self.upgrades['fearless'] = (1, 5, "Fearless", "Your Lion becomes [holy] and is not afraid of [Dark] or [Undead] units, and gains a holy leaping attack with 6 range.", [Tags.Holy])

	def get_description(self):
		return ("Call forth a cowardly lion, who gains the fear debuff if any [dark], or [undead] units are within 3 tiles and the wizard is not within 3 tiles.\n"
				"Cowardly Lions have [{minion_health}_HP:minion_health] and an attack which deals [{minion_damage}_physical:physical] damage.").format(**self.fmt_dict())

	def get_extra_examine_tooltips(self):
		return [CowardlyLion(), self.spell_upgrades[0], RedLion(), IceLion(), StarLion(), self.spell_upgrades[1], self.spell_upgrades[2]]

	def cast(self, x, y):
		unit = CowardlyLion()
		if self.get_stat('fearless'):
			unit.tags.append(Tags.Holy)
			leap = LeapAttack(damage=self.get_stat('minion_damage'), range=self.get_stat('minion_range',base=6), is_leap=True, damage_type=Tags.Holy)
			unit.spells.insert(0, leap)
		else:
			unit.apply_buff(CowardlyBuff(self))
		if self.get_stat('pride'):
			lion = random.choice([[Tags.Fire, RedLion], [Tags.Ice, IceLion], [Tags.Arcane, StarLion]])
			summon_lion = SimpleSummon(spawn_func=lion[1], num_summons=1, cool_down=10)
			unit.tags.append(lion[0])
			unit.spells.insert(0,summon_lion)
		if self.get_stat('roar'):
			unit.tags.append(Tags.Dark)
			grant_minion_spell(WaveOfDread, unit, self.caster, 10, True)
		apply_minion_bonuses(self, unit)
		self.summon(unit, Point(x,y))
		yield



class Ennervate(Buff):
	def on_init(self):
		self.name = "Weakened"
		self.stack_type = STACK_INTENSITY
		self.buff_type = BUFF_TYPE_CURSE
		self.color = Tags.Arcane.color
		self.global_bonuses['damage'] = -5
		self.owner_triggers[EventOnSpellCast] = self.on_cast
		
	def on_cast(self, evt):
		self.owner.level.queue_spell(self.clear_buffs())
		
	def clear_buffs(self):
		self.owner.remove_buff(self)
		yield

class Innervate(Buff):
	def __init__(self, spell):
		Buff.__init__(self)
		self.spell = spell
		if self.spell.get_stat('minion'):
			self.global_bonuses['minion_damage'] = 3
			self.global_bonuses['minion_health'] = 3
		if self.spell.get_stat('extend'):
			self.global_bonuses['duration'] = 2
			self.global_bonuses['minion_duration'] = 2
			
	def on_init(self):
		self.name = "Empowered"
		self.stack_type = STACK_INTENSITY
		self.buff_type = BUFF_TYPE_BLESS
		self.color = Tags.Arcane.color
		self.global_bonuses['damage'] = 5
		self.owner_triggers[EventOnSpellCast] = self.on_cast
		
	def on_cast(self, evt):
		self.owner.level.queue_spell(self.clear_buffs())
		
	def clear_buffs(self):
		self.owner.remove_buff(self)
		yield

class PowerShift(Spell):
	def on_init(self):
		self.name = "Power Shift"
		self.tags = [Tags.Arcane, Tags.Enchantment]
		self.level = 4 ##Aiming for 3-5. Not sure how strong this will be with upgrades? Its -damage effect causes it to be a bit safer than most enchantment spells.
		self.asset = ["TcrsCustomModpack", "Icons", "power_shift"] ##Maybe remove the small arrows? Not important really.

		self.max_charges = 4
		self.range = 10
		self.duration = 5
		
		self.bonus = 5
		self.can_target_empty = False
		self.can_target_self = True

		self.upgrades['cleave'] = (1, 5, "Cleaver", "If you are within the group, and at least 5 enemies are connected, cast your Death Cleave spell.", [Tags.Dark])
		self.upgrades['extend'] = (1, 3, "Extend Buffs", "Each stack of the buff also gives 2 duration and 2 minion duration to the next spell.")
		self.upgrades['minion'] = (1, 3, "Empower Minions", "Each stack of the buff also gives 3 minion health and 3 minion damage to the next spell.")

	def get_description(self):
		return ("All enemy units in a connected group lose 5 damage. Grant yourself a damage buff for each enemy affected, granting you 5 damage.\n"
				"Allies connect the group, but are unaffected.\n"
				"The debuff lasts [{duration}_turns:duration]. The buff lasts 1 turns."
				"The debuff and buff are both removed after one spell is cast.").format(**self.fmt_dict())

	def cast(self, x, y):
		tiles = self.caster.level.get_connected_group_from_point(x, y, check_hostile=None)
		wizard = False
		enemies = []
		for t in tiles:
			u = self.caster.level.get_unit_at(t.x, t.y)
			if are_hostile(self.caster, u):
				enemies.append(u)
				u.apply_buff(Ennervate(), 5)
			else:
				if u.is_player_controlled:
					wizard = True
		
		count = len(enemies)
		if wizard and count >= 5 and self.get_stat('cleave'):
			spell = self.caster.get_or_make_spell(DeathCleaveSpell)
			self.caster.level.act_cast(self.caster, spell, self.caster.x, self.caster.y, pay_costs=False)
		for i in range(count):
			self.caster.apply_buff(Innervate(self), 2)
		
		yield
		
	def get_impacted_tiles(self, x, y):
		return self.caster.level.get_connected_group_from_point(x, y, check_hostile=None)



class TreeFormBuff(Buff):
	def __init__(self, spell):
		Buff.__init__(self)
		self.spell = spell
		self.transform_asset = ["TcrsCustomModpack", "Units", "player_tree_form"]
		self.name = "Spread Your Roots"
		self.buff_type = BUFF_TYPE_BLESS
		self.color = Tags.Nature.color
		self.description = "Each turn you cast poison sting at random enemies."
		
		if self.spell.get_stat('evil'):
			self.resists[Tags.Dark] = 75
		self.resists[Tags.Poison] = 100
		self.stack_type = STACK_TYPE_TRANSFORM
		self.owner_triggers[EventOnMoved] = self.on_move
		self.owner_triggers[EventOnSpellCast] = self.on_cast
		if self.spell.get_stat('fertilize'):
			self.global_triggers[EventOnDeath] = self.on_death
		self.counter = 0
		self.fertilize = False
		
	def on_move(self, evt):
		if not self.spell.get_stat('uproot'):
			self.owner.remove_buff(self)
		
	def on_advance(self):
		if self.spell.get_stat('evil'):
			unit = Ghost()
			apply_minion_bonuses(self, unit)
			self.spell.caster.level.summon(self.owner, unit, Point(self.owner.x,self.owner.y))
		self.fertilize = False
		self.counter += 1 ##self.owner.level.can_see(self.owner.x, self.owner.y, u.x, u.y) use LOS if too strong
		units = [u for u in self.owner.level.units if self.owner.level.are_hostile(u, self.owner)]
		if units == []:
			return
		random.shuffle(units)
		for i in range(self.spell.get_stat('num_targets', base=1)):
			targ = units.pop(0)
			spell = self.owner.get_or_make_spell(PoisonSting)
			self.owner.level.act_cast(self.owner, spell, targ.x, targ.y, pay_costs=False)
			if self.counter >= 5:
				s = self.owner.get_or_make_spell(ToxinBurst)
				self.owner.level.act_cast(self.owner, s, targ.x, targ.y, pay_costs=False)
			if units == []:
				break
			
	def on_cast(self, evt):
		if not self.spell.get_stat('uproot'):
			return
		if evt.spell.level < 3 or not Tags.Nature in evt.spell.tags:
			return
		self.turns_left += self.spell.get_stat('duration', base=3)
		
	def on_death(self, evt):
		if not (Tags.Living in evt.unit.tags or Tags.Nature in evt.unit.tags):
			return
		if self.fertilize == True:
			return
		self.fertilize = True
		s = self.owner.get_or_make_spell(ToxicSpore)
		self.owner.level.act_cast(self.owner, s, evt.unit.x, evt.unit.y, pay_costs=False)

class TreeFormSpell(Spell):
	def on_init(self):
		self.tags = [Tags.Nature, Tags.Enchantment]
		self.name = "Spread your Roots"
		self.level = 5 ##Attempting to make this a level 5.
		self.asset = ["TcrsCustomModpack", "Icons", "spread_roots"]

		self.max_charges = 1
		self.range = 0
		self.duration = 25
		self.num_targets = 1

		self.upgrades['evil'] = (1, 2, "Spreading Evil", "Gain 75 [Dark] resist during the effect, and summon a ghost nearby you each turn.", [Tags.Dark])
		self.upgrades['fertilize'] = (1, 4, "Fertilize", "Each turn, the first time a [Living] or [Nature] unit dies, cast your Toxic Spore at that location.", [Tags.Conjuration])
		self.upgrades['uproot'] = (1, 2, "Uproot", "This buff lasts [3:duration] more turns each time you cast a level 3 or higher nature spell and no longer ends when you move.")
		
	def on_applied(self):
		self.owner.transform_anim = ["TcrsCustomModpack", "Units", "player_tree_form"]
		

	def cast(self, x, y):
		self.caster.apply_buff(TreeFormBuff(self), self.get_stat('duration'))
		yield

	def get_description(self):
		return ("Each turn, cast your poison sting at up to [{num_targets}:num_targets] random enemy. If the buff lasts more than 5 turns, also cast toxin burst.\n"
				"Gain 100 poison resist during the effect.\nLasts up to 25 turns, and ends when you move.").format(**self.fmt_dict())



def AnimatedTrinket():
	unit = Unit()
	unit.name = "Knick-Knack"
	unit.max_hp = 2
	unit.shields = 3
	unit.flying = True
	unit.spells.append(SimpleMeleeAttack(6))
	unit.buffs.append(TeleportyBuff())
	unit.tags = [Tags.Arcane, Tags.Metallic, Tags.Construct]
	return unit

class AnimateClutter(Spell):
	def on_init(self):
		self.name = "Animate Clutter"
		self.tags = [Tags.Arcane, Tags.Metallic, Tags.Conjuration]
		self.asset = ["TcrsCustomModpack", "Icons", "animate_clutter"]
		self.level = 3
		
		self.max_charges = 5
		self.range = 0
		self.minion_health = 2
		self.minion_damage = 6
		
		self.suffixes = ['claw', 'dagger', 'disk', 'fang', 'flag', 'horn', 'hourglass', 'lens', 'orb', 'scale', 'sigil', 'tome']
		self.asset_list = []
		
		self.tagdict = ScrollConvertor()
		self.tagdict[Tags.Metallic] = [MetalShard,LivingMetalScroll]
		self.tagdict[Tags.Chaos] = [Improvise,LivingChaosScroll]

		self.upgrades['sorcerer'] = (1, 1, "Chromatic Wizard", "Instead of animating trinkets, summon a living scroll for each tag in each spell you know.", [Tags.Sorcery])
		self.upgrades['selfequip'] = (1, 1, "Piper Linker", "Your animated Pipes and Links equip a copy of themselves.")
		self.upgrades['sigil'] = (1, 1, "Sigilite", "Your sigils can summon their associated unit every 15 turns.")


	def get_description(self):
		return ("Animate your trinkets into allies. Each trinket is a flying, teleporting, melee attacker which "
				"deals [{minion_damage}_physical:physical] damage and has [{minion_health}_HP:minion_health] and 3 shields.").format(**self.fmt_dict())

	def cast(self, x, y):
		if self.get_stat('sorcerer'):
			for s in self.caster.spells:
				for tag in s.tags:
					if tag in self.tagdict:
						unit = self.tagdict[tag][1]()
						spell = self.caster.get_or_make_spell(self.tagdict[tag][0])
						spell.statholder = self.caster
						unit.spells.append(spell)
						self.summon(unit, radius=4, sort_dist=False)
		else:
			if self.caster.trinkets == []:
				unit = AnimatedTrinket()
				suffix = random.choice(self.suffixes)
				unit.asset = ["TcrsCustomModpack", "Units", "AnimateTrinket" , "trinket_" + suffix + "_anim"]
			
			self.check_assets()
			index = 0
			for t in self.caster.trinkets:
				unit = AnimatedTrinket()
				unit.asset =  self.asset_list[index]
				index += 1
				apply_minion_bonuses(self, unit)
				self.summon(unit)
				if self.get_stat('sigil') and "Sigil" in t.name:
					spell = SimpleSummon(spawn_func=t.spawn_fn, num_summons=1, cool_down=10, duration=0, sort_dist=False)
					spell.owner = unit ##To avoid NoneType can't pay costs errors.
					spell.caster = unit
					spell.statholder = unit
					unit.spells.append(spell)
				if self.get_stat('selfequip'):
					#print(t)
					split_str = (t.name.lower().split(' '))
					if not len(split_str) == 1:
						if split_str[1] == 'pipe':
							trinket = lambda : CursePipe(t.name, t.buff_t, t.duration, t.num_targets, t.cool_down, t.visual_tag)
							unit.equip(trinket())
						elif split_str[1] == 'links':
							trinket = lambda : PrinceOfRuinLike(t.name, t.tags)
							unit.equip(trinket())
		yield
		
	def check_assets(self):
		count = len(self.caster.trinkets)
		asset_list = []
		if count == len(self.asset_list):
			return None
		for t in self.caster.trinkets:
			tname = t.name.lower()
			split_str = (tname.split(' '))
			if split_str[-1] in self.suffixes:
				suffix = split_str[-1]
				asset = ["TcrsCustomModpack", "Units", "AnimateTrinket" , "trinket_" + suffix + "_anim"]
				asset_list.append(asset)
			else:
				n = tname.replace(' ','_')
				asset = ["TcrsCustomModpack", "Units", "AnimateTrinket" , n + "_anim"]

				path = os.path.join(os.path.curdir, "mods\\TcrsCustomModpack\\Units\\AnimateTrinket\\" + n + "_anim.png")
				#print(path)
				if not os.path.exists(path):
					asset = ["TcrsCustomModpack", "Units", "AnimateTrinket" , "animated_teapot"] ##Real fantasia vibes here
				asset_list.append(asset)

		self.asset_list = asset_list



class HP_X_Damage(Spell):
	def on_init(self):
		self.name = "Hp%Distance:Dmg"
		self.tags = [Tags.Arcane, Tags.Sorcery]
		self.level = 4 ##Difficult to measure its effectiveness, because it's as good as you are at choosing realms +  your arithmetic
		self.asset = ["TcrsCustomModpack", "Icons", "hp_distance"]

		self.max_charges = 10
		self.range = 10
		self.damage = 10
		self.damage_type = [Tags.Arcane]
		
		self.can_target_self = False
		self.requires_los = False

		self.upgrades['threeseven'] = (1, 2, "3s and 7s", "Always affects all units whose current hp ends in 3 or 7")
		self.upgrades['prime'] = (1, 1, "Prime Power", "Also affects all units whose current hp is a prime number.")
		self.upgrades['flare'] = (1, 6, "Lvl3Flare", "If the realm number is evenly divisible by 3, deal [holy] or [fire] damage to all units as well.", [Tags.Fire, Tags.Holy])

	def get_description(self):
		return ("Calculate the distance value, X, which is equal to the number of tiles between yourself and target tile.\n"
				"Then for every unit deal [{damage}_Arcane:Arcane] damage to it, if its current hp is evenly divisible by X. Silences affected units for 3 turns.").format(**self.fmt_dict())

	def get_targetable_tiles(self):
		rad = self.get_stat('range')
		points = []
		for i in range(-rad, rad + 1):
			points.append(Point(self.caster.x+i, self.caster.y))
			if i != 0:
				points.append(Point(self.caster.x, self.caster.y+i))
		return points

	def isprime(self, x):
		if x > 2:
			y = math.ceil(x / 2)
		elif x == 2:
			return True
		else:
			return False
		for i in range(2,y):
			if x % i == 0:
				return True
		return False
		
	def cast(self, x, y):
		diffx = self.caster.x - x
		diffy = self.caster.y - y
		if diffx == 0:
			divisor = abs(diffy)
		elif diffy == 0:
			divisor = abs(diffx)
			
		units = list(self.caster.level.units)
		for unit in units:
			if unit == None:
				continue
			if unit.cur_hp % divisor == 0:
				unit.deal_damage(self.get_stat('damage'), Tags.Arcane, self)
				unit.apply_buff(Silence(),3)
			if self.get_stat('threeseven') and (unit.cur_hp % 10 == 7 or unit.cur_hp % 10 == 3):
				unit.deal_damage(self.get_stat('damage'), Tags.Arcane, self)
				unit.apply_buff(Silence(),3)
			if self.get_stat('prime') and not self.isprime(unit.cur_hp):
				unit.deal_damage(self.get_stat('damage'), Tags.Arcane, self)
				unit.apply_buff(Silence(),3)
			if self.get_stat('flare') and self.caster.level.level_no % 3 == 0:
				tag = random.choice([Tags.Fire, Tags.Holy])
				unit.deal_damage(self.get_stat('damage'), tag, self)
				unit.apply_buff(Silence(),3)

		yield



class Overload(Spell):
	def on_init(self):
		self.name = "Overload"
		self.tags = [Tags.Lightning, Tags.Sorcery]
		self.level = 4 ##Aiming for level 4,  high charge count, weaker than chain lightning for huge groups but much stronger on connected groups?
		self.asset = ["TcrsCustomModpack", "Icons", "overload"]

		self.max_charges = 15
		self.damage = 30
		self.damage_type = [Tags.Lightning]
		self.range = 10
		self.duration = 2

		self.can_target_empty = False

		self.upgrades['ion'] = (1, 4, "Ionizing", "Also deals arcane damage. For each enemy killed, apply the faetouched modifier to a random non-arcane ally.", [Tags.Arcane])
		self.upgrades['power'] = (1, 3, "Crackle with Power", "If you are part of the connected group, cast lightning bolt on 2 random tiles for each unit in the group.")
		self.upgrades['conductive'] = (1, 2, "Superconductivity", "If there are any metallic units in the group, cast conductivity on up to [5:num_targets] of them before dealing damage.") ##TODO empower the spell for each metallic enemy

	def get_description(self):
		return ("Deals [{damage}_lightning:lightning] damage to a connected group of units."
				" Metallic units are stunned and take [physical] damage.").format(**self.fmt_dict())

	def get_impacted_tiles(self, x, y):
		candidates = set([Point(x, y)])
		unit_group = set()
		while candidates:
			candidate = candidates.pop()
			unit = self.caster.level.get_unit_at(candidate.x, candidate.y)
			if unit and unit not in unit_group:
				unit_group.add(unit)
				for p in self.caster.level.get_adjacent_points(Point(unit.x, unit.y), filter_walkable=False):
					candidates.add(p)
		return list(unit_group)
	
	def cast(self, x, y ):
		tiles = self.get_impacted_tiles(x,y)
		units = []
		wizard = False
		for t in tiles:
			u = self.caster.level.get_unit_at(t.x, t.y)
			if u == None:
				continue
			if u.name == 'Wizard':
				wizard = True
			units.append(u)

		kills = 0
		count = self.get_stat('num_targets',base=5)
		for u in units:
			if Tags.Metallic in u.tags:
				self.caster.level.deal_damage(u.x, u.y, self.get_stat('damage'), Tags.Physical, self)
				u.apply_buff(Stun(),2)
				if self.get_stat('conductive') and count > 0:
					count -= 1
					spell = self.owner.get_or_make_spell(ConductanceSpell)
					self.caster.level.act_cast(self.caster, spell, u.x, u.y, pay_costs=False, queue=False)
			self.caster.level.deal_damage(u.x, u.y, self.get_stat('damage'), Tags.Lightning, self)
			if self.get_stat('ion'):
				self.caster.level.deal_damage(u.x, u.y, self.get_stat('damage'), Tags.Arcane, self)
			if not u.is_alive() and self.get_stat('ion'):
				kills += 1
				
		if self.get_stat('ion'):
			allies = [a for a in self.caster.level.units if not are_hostile(a, self.caster) and not Tags.Arcane in a.tags and not a.is_player_controlled]
			if allies:
				random.shuffle(allies) ##set size of allies equal to index[kill] to shorten list sometime
				for i in range(kills):
					print(i)
					allies[i].Anim = None
					BossSpawns.apply_modifier(BossSpawns.Faetouched, allies[i])
		
		if self.get_stat('power') and wizard:
			for i in range(len(units) * 2):
				spell = self.caster.get_or_make_spell(LightningBoltSpell)
				randpoint = Point(random.randint(0,self.caster.level.height-1), random.randint(0, self.caster.level.width-1))
				while self.caster.level.tiles[randpoint.x][randpoint.y].is_wall():
					randpoint = Point(random.randint(0,self.caster.level.height-1), random.randint(0, self.caster.level.width-1))
				for s in self.caster.level.act_cast(self.caster, spell, randpoint.x, randpoint.y, pay_costs=False, queue=False):
					yield

		yield



class UtterDestruction(Spell):
	def on_init(self):
		self.name = "Total Annihilation"
		self.tags = [Tags.Dark, Tags.Sorcery]
		self.level = 6
		self.asset = ["TcrsCustomModpack", "Icons", "total_annihilation"]

		self.max_charges = 1
		self.damage = 20
		self.damage_type = [Tags.Dark]
		self.range = 0
		
		self.max_channel = 20
		self.channel_cast = False
		self.can_target_self = True
		self.tile_index = 0
		self.tiles = []

		self.upgrades['devourmind'] = (1, 2, "Absolute Insanity", "Cast your Devour Mind on every target in the wave.", [Tags.Arcane])
		self.upgrades['dedication'] = (1, 3, "Complete Dedication", "If the wave reaches the end of the realm, cast your Heaven's Wrath.", [Tags.Holy])
		self.upgrades['max_channel'] = (255, 2, "Supreme Destruction", "The wave gains 255 more turns of max channeling.")

	def get_description(self):
		return ("A wave of destruction moves from the left side of the realm to the right side, advancing as you channel. "
				"The amount of tiles that are affected is a random number between this spell's damage value, and 10 times that value.\n"
				"Deal [{damage}_dark:dark] damage to every unit in an affected tile. Will damage the wizard but only deals half damage.").format(**self.fmt_dict())

	def cast(self, x, y, channel_cast=False):
		if self.tiles == []:
			tiles = self.caster.level.iter_tiles()
			for t in tiles:
				self.tiles.append(t)

		if not channel_cast:
			self.tile_index = 0
			self.caster.apply_buff(ChannelBuff(self.cast, Point(x, y)), self.get_stat('max_channel'))
			return
		
		damage = self.get_stat('damage')
		count = random.randint(damage, damage * 10)
		for i in range(count):
			if self.tile_index == len(self.tiles) - 1:
				self.tile_index = 0
				if self.get_stat('dedication'):
					spell = self.caster.get_or_make_spell(Spells.HeavensWrath)
					self.caster.level.act_cast(self.caster, spell, x, y, pay_costs=False, queue=True)
				break
			t = self.tiles[self.tile_index]
			self.tile_index += 1
			
			if self.get_stat('devourmind'):
				spell = self.caster.get_or_make_spell(Spells.MindDevour)
				if self.caster.level.get_unit_at(t.x, t.y) != None:
					self.caster.level.act_cast(self.caster, spell, t.x, t.y, pay_costs=False, queue=True)
			u = self.owner.level.get_unit_at(t.x, t.y)
			if u and u.is_player_controlled:
				self.owner.level.deal_damage(t.x, t.y, self.get_stat('damage') // 2, Tags.Dark, self)
			else:
				self.owner.level.deal_damage(t.x, t.y, self.get_stat('damage'), Tags.Dark, self)
		yield



class DominoeAttack(Spell):
	def on_init(self):
		self.name = "Dominoe Smash"
		self.tags = [Tags.Metallic, Tags.Sorcery]
		self.level = 3 ##Comparable to death touch and my own absorb. I like this spell but it seems very weak. Its upgrades are cool to compensate.
		self.asset = ["TcrsCustomModpack", "Icons", "dominoe_icon"]
		
		self.max_charges = 12
		self.damage = 50
		self.damage_type = [Tags.Physical]
		self.range = 1

		self.melee = True
		self.cast_on_walls = True

		self.upgrades['thunder'] = (1, 3, "Thunderbone's Game", "Summon an electric bone shambler with 8 max hp for each affected unit, if 2 or more units are affected.", [Tags.Lightning])
		self.upgrades['bones'] = (1, 3, "Throw the bones", "Each struck unit has a 1/6 chance of summoning a Bone Knight", [Tags.Dark])
		self.upgrades['dominator'] = (1, 3, "Fives and Threes", "If exactly 3, or a multiple of 3, units are targeted, cast your Dominate on 5 viable enemies.", [Tags.Enchantment])

	def get_description(self):
		return ("Deal [{damage}_physical:physical] to one tile in melee range, and then repeat on one enemy unit adjacent to the target."
				" This repeats any number of times, but never on the same units.\nIf multiple units are adjacent pick the first unit going clockwise around the point, starting at the top left tile, but this ends the spell.").format(**self.fmt_dict())

	def get_extra_examine_tooltips(self):
		elec_shambler = BoneShambler(16)
		BossSpawns.apply_modifier(BossSpawns.Stormtouched, elec_shambler)
		return [self.spell_upgrades[0], elec_shambler, self.spell_upgrades[1], BoneKnight(), self.spell_upgrades[2]]

	def get_impacted_tiles(self, x, y):
		units = []
		point = Point(x, y)
		if self.caster.level.get_unit_at(x, y) != None:
			units = [self.caster.level.get_unit_at(x, y)]
		while point != None:
			adj_units = []
			u = None
			for p in self.caster.level.get_adjacent_points(point, filter_walkable=False):
				u = self.caster.level.get_unit_at(p.x, p.y)
				if u != None and are_hostile(self.caster, u) and u not in units:
					adj_units.append(u)
			
			if len(adj_units) == 1:
				units.append(adj_units[0])
				point = Point(adj_units[0].x, adj_units[0].y)
			elif adj_units == []:
				point = None
			else:
				units.append(adj_units[0])
				point = None

		return units

	# def get_impacted_tiles_OLD(self, x, y):
	# 	units = []
	# 	u = self.caster.level.get_unit_at(x, y)
	# 	if u == None:
	# 		for p in self.caster.level.get_adjacent_points(Point(x, y), filter_walkable=False):
	# 			u = self.caster.level.get_unit_at(p.x, p.y)
	# 			if u != None:
	# 				break
	# 	if u == None:
	# 		return None
	# 	while u != None:
	# 		units.append(u)
	# 		temp_units = []
	# 		for p in self.caster.level.get_adjacent_points(Point(u.x, u.y), filter_walkable=False):
	# 			u = self.caster.level.get_unit_at(p.x, p.y)
	# 			if u != None and u != self.caster and u not in units:
	# 				temp_units.append(u)
	# 		if len(temp_units) != 1:
	# 			u = None
	# 		else:
	# 			u = temp_units[0]

	# 	return units

	def thunder_shambler(self, multiplier):
		unit = BoneShambler(8 * multiplier)
		BossSpawns.apply_modifier(BossSpawns.Stormtouched, unit)
		return unit

	def cast(self, x, y):
		units = self.get_impacted_tiles(x, y)
		for u in units:
			self.caster.level.deal_damage(u.x, u.y, self.get_stat('damage'), Tags.Physical, self)
			if self.get_stat('bones'):
				if random.randint(1,6) == 6: ##TODO incorporate chance attribute
					unit = BoneKnight()
					apply_minion_bonuses(self, unit)
					self.caster.level.summon(self.caster, unit, Point(u.x, u.y))

		if self.get_stat('dominator') and len(units) % 3 == 0:
			spell = self.caster.get_or_make_spell(Dominate)
			targets = [t for t in self.caster.level.units if are_hostile(t, self.caster) and t.max_hp <= spell.hp_threshold]
			if targets:
				random.shuffle(targets)
				for i in range(min(5, len(targets))):
					for s in self.caster.level.act_cast(self.caster, spell, targets[i].x, targets[i].y, pay_costs=False, queue=False):
						yield
		if self.get_stat('thunder') and len(units) >= 2:
			unit = self.thunder_shambler(len(units))
			apply_minion_bonuses(self, unit)
			self.summon(unit)

		yield



class UnstableStormBuff(Buff):
	def __init__(self, spell):
		self.spell = spell
		Buff.__init__(self)
		self.stack_type = STACK_REPLACE
		self.color = Tags.Arcane.color
		self.buff_type = BUFF_TYPE_BLESS
		self.storm_count = 0
		#self.asset = ['status', 'multicast']
		self.d_types = [Tags.Lightning, Tags.Arcane, Tags.Dark]
		if self.spell.get_stat('lessdmg'):
			self.d_types.remove(random.choice([Tags.Lightning, Tags.Arcane, Tags.Dark]))

	def on_init(self):
		self.name = "Unstable Spell Storm"
		self.description = "Whenever you cast a non-conjuration, non-self cast spell, copy it once on a random target for each spell you've cast since the buff was applied."
		##Perhaps include enchantments? 
		self.can_copy = True
		self.owner_triggers[EventOnSpellCast] = self.on_spell_cast

	def on_spell_cast(self, evt):
		if evt.spell.item:
			return
		if Tags.Conjuration in evt.spell.tags:
			return
		self.storm_count += 1
		if self.can_copy:
			self.can_copy = False
			for i in range(self.storm_count):
				eligible_units = [u for u in self.owner.level.units if not u.is_player_controlled]
				if eligible_units == []:
					continue
				unit = random.choice(eligible_units)
				if self.spell.get_stat('favour') and are_hostile(self.owner, unit):
					unit = random.choice(eligible_units)
				if evt.spell.can_pay_costs(): #evt.spell.can_cast(unit.x, unit.y)
					evt.caster.level.act_cast(evt.caster, evt.spell, unit.x, unit.y, pay_costs=False)
					for t in self.d_types:
						self.owner.level.deal_damage(self.owner.x, self.owner.y, 1, t, self) ##TODO should this be multiplied by the  spells level so you really kill yourself?
						if self.spell.get_stat('spendhp'):
							self.owner.level.event_manager.raise_event(EventOnSpendHP(self.owner, 1), self.owner)
			evt.caster.level.queue_spell(self.reset())

	def reset(self):
		self.can_copy = True
		yield

class UnstableSpellStorm(Spell):
	def on_init(self):
		self.name = "Unstable Spell Storm"
		self.tags = [Tags.Blood, Tags.Lightning, Tags.Arcane, Tags.Enchantment]
		self.level = 8 ##Undeniably a level 8 spell. Probably needs a nerf before even being released. It either kills the entire stage or you. Which is the goal.
		self.asset = ["TcrsCustomModpack", "Icons", "unstable_spell_storm"]

		self.hp_cost = 99
		self.max_charges = 1
		self.range = 0
		self.duration = 10

		self.upgrades['lessdmg'] = (1, 3, "Minimal Backlash", "Take damage from 2 of the types instead of all 3. Changes each time the buff is applied.")
		self.upgrades['favour'] = (1, 2, "Favourable Odds", "If an ally is chosen as the target of a copied spell, randomly target another unit instead, triggers once per spell.")
		self.upgrades['spendhp'] = (1, 1, "Blood", "The damage from copying spells counts as spending HP for blood spells and skills.")


	def get_description(self):
		return ("For 10 turns, each time you cast a non-self targeting spell, make a copy of that spell targeting a random "
				" unit for each spell you've cast during the effect. For each copy made, take 1 [arcane], 1 [lightning], and 1 [dark] damage.\n"
				"The spells will not target you. Does not apply to conjuration spells.").format(**self.fmt_dict())

	def cast(self, x, y):
		self.caster.apply_buff(UnstableStormBuff(self), self.get_stat('duration'))
		yield



class DespawnHorseman(Buff):
	def __init__(self, unit):
		Buff.__init__(self)
		self.unit = unit
		self.buff_type = BUFF_TYPE_PASSIVE
	
	def on_advance(self):
		b = self.owner.get_buff(ChannelBuff)
		if not b or not b.spell == TheSecondSeal:
			if self.unit.is_alive():
				unit.kill()

class RedRiderBerserkingSpell_Global(RedRiderBerserkingSpell):

	def on_init(self):
		self.name = "Strife"
		self.description = "Berserk all enemies for 3 turns, except the wizard."
		self.cool_down = 13
		self.duration = 3
		self.range = 0

	def get_ai_target(self):
		for u in self.caster.level.get_units_in_los(self.caster):
			if are_hostile(self.caster, u) and not u.is_player_controlled:
				return self.caster
		return None

	def cast(self, x, y):
		for u in self.caster.level.units:
			if are_hostile(self.caster, u) and not u.is_player_controlled:
				u.apply_buff(BerserkBuff(), self.get_stat('duration'))
				yield

def RedRiderMod():
	unit = RedRider()
	unit.spells.pop(0)
	unit.spells.pop(0)
	unit.spells.pop(0)
	unit.spells.insert(0, RedRiderBerserkingSpell_Global())
	unit.spells.append(SimpleMeleeAttack(damage=34,damage_type=Tags.Fire))
	return unit

class TheSecondSeal(Spell):
	def on_init(self):
		self.name = "The Second Seal"
		self.tags = [Tags.Holy, Tags.Conjuration, Tags.Chaos]
		self.level = 6 ##Actually not very good, it's like a weaker form of word of madness that sometimes kills enemies. Can probably have more charges, maybe infinite?
		self.asset = ["TcrsCustomModpack", "Icons", "thesecondseal"]

		self.max_charges = 10
		self.range = 5
		
		example = RedRiderMod()
		self.minion_health = example.max_hp
		self.minion_damage = example.spells[2].damage
		self.minion_duration = 1
		
		self.unit = None
		
		self.upgrades['sustained'] = (1, 3, "Monarch's Voice", "Each turn you channel now adds an extra [1:minion_duration] turns to its lifetime, scaling with minion duration.")
		self.upgrades[('lasting','duration')] = ([1,5], 2, "Cry Havoc", "The Rider's Berserk skill lasts for this spell's duration stat instead of a fixed 3 turns.", [Tags.Enchantment])
		self.upgrades['faster'] = (1, 2, "Let Slip, the Rider", "The Rider gains the [lightning] tag and is permanently hasted, taking two turns instead of one. It also gains clarity after being disabled.", [Tags.Lightning])
		self.upgrades['dogs'] = (1, 5, "Dogs of War", "The Rider can now summon hellhounds on a 6 turn cooldown.", [Tags.Fire])



	def get_description(self):
		return ("Summon The Red Rider, a powerful ally that can berserk all enemies on the map for 3 turns, and heals when any enemy takes [fire] or [physical] damage.\n"
				"The Rider lasts [1:minion_duration] turn, and each turn you channel this spell adds 1 turn to its lifetime. Can be channeled forever.").format(**self.fmt_dict())

	def get_extra_examine_tooltips(self):
		return [RedRiderMod()] + self.spell_upgrades

	def cast(self, x, y, channel_cast=False):
		if not channel_cast:
			unit = RedRiderMod()
			if self.get_stat('lasting'):
				duration = self.get_stat('duration', base=5)
				unit.spells[0].duration = duration
			if self.get_stat('dogs'):
				spell = SimpleSummon(self.houndofwar, num_summons=6, sort_dist=False, cool_down=6, radius=6, duration = 6)
				unit.spells.insert(0,spell)
			apply_minion_bonuses(self, unit)
			self.unit = unit
			self.caster.level.summon(self.caster, unit, Point(x,y))
			unit.turns_to_death = 1
			self.caster.apply_buff(ChannelBuff(self.cast, target=self.unit), self.get_stat('max_channel'))
			if self.get_stat('faster'):
				unit.tags.append(Tags.Lightning)
				unit.apply_buff(HasteBuff())
				unit.gets_clarity = True
			return
		else:
			if not self.unit or not self.unit.is_alive():
				return
			self.unit.turns_to_death += 1
			if self.get_stat('sustained'):
				self.unit.turns_to_death += self.get_stat('duration',base=2)
		yield

	def houndofwar(self):
		dog = HellHound()
		apply_minion_bonuses(self, dog)
		return dog



class MoguiSplitting(Buff):
	def __init__(self, spell):
		self.spell = spell
		Buff.__init__(self)

	def on_init(self):
		self.name = "Rain Demon"
		self.description = "Each turn create another mogui if soaked or in a Rain Cloud. Destroys the cloud and loses soaked each turn."
		self.owner_triggers[EventOnDeath] = self.on_death

	def on_advance(self):
		turns_remaining = self.owner.turns_to_death - 1
		if turns_remaining <= 1:
			return
		unit = None
		cloud = self.owner.level.tiles[self.owner.x][self.owner.y].cloud
		if self.spell.get_stat('cold'):
			valid_clouds = (BlizzardCloud, RainCloud)
		elif self.spell.get_stat('claws'):
			valid_clouds = (StormCloud, RainCloud)
		else:
			valid_clouds = (RainCloud)
		if cloud and isinstance(cloud, valid_clouds):
			unit = self.spell.make_mogui(turns_remaining)
			cloud.kill()
		if self.owner.has_buff(SoakedBuff):
			unit = self.spell.make_mogui(turns_remaining)
			self.owner.remove_buffs(SoakedBuff)
		if unit == None:
			return
		self.owner.level.summon(self.spell.owner, unit, target=Point(self.owner.x, self.owner.y), team=self.owner.team)

	def on_death(self, evt):
		if not self.spell.get_stat('possess'):
			return
		dominate = self.spell.owner.get_or_make_spell(Dominate)
		dominate.caster = self.owner
		dominate.owner = self.owner
		dominate.statholder = self.spell.owner

		targets = [u for u in self.owner.level.get_units_in_ball(self.owner, radius=dominate.range) if are_hostile(u, self.owner)]
		targets_hp = []
		if dominate.get_stat('check_cur_hp'):
			targets_hp = [u for u in  targets if u.cur_hp <= dominate.get_stat('hp_threshold')]
		else:
			targets_hp = [u for u in  targets if u.max_hp <= dominate.get_stat('hp_threshold')]
		if targets_hp == []:
			return
		
		target = random.choice(targets_hp)
		self.owner.level.act_cast(self.owner, dominate, target.x, target.y, pay_costs=False) ##TODO this has crashed before. This still crashes sometimes, idk what's wrong now.

def Mogui():
	unit = Unit()
	unit.name = "Mogui"
	unit.tags = [Tags.Nature, Tags.Demon]
	if water_tag in Tags:
		unit.tags.append(Tags.Water)
	unit.asset = ["TcrsCustomModpack", "Units", "mogui"]
	unit.max_hp = 24
	unit.resists[Tags.Holy] = -100
	unit.resists[Tags.Dark] = 50

	unit.spells.append(SimpleMeleeAttack(damage=5,damage_type=Tags.Physical))
	return unit

class RainDemonMogui(Spell):
	def on_init(self):
		self.name = "Rain Demon Mogui"
		self.tags = [Tags.Nature, Tags.Chaos, Tags.Conjuration]
		if water_tag in Tags:
			self.tags.append(Tags.Water)
		self.level = 6
		self.max_charges = 2
		self.asset =  ["TcrsCustomModpack", "Icons", "mogui_icon"]
		
		self.minion_health = 40
		self.minion_damage = 5
		self.minion_duration = 25

		self.upgrades['cold'] = (1, 4, "Cold Shower", "Mogui gain your icicle spell on an 8 turn cooldown. They also multiply on blizzard clouds.", [Tags.Ice])
		self.upgrades[('claws','minion_range')] = ([1,4], 2, "Lightning Claws", "Mogui gain a leaping [Lightning] melee attack with 4 tiles of range. They also multiply on storm clouds.", [Tags.Lightning])
		self.upgrades['possess'] = (1, 2, 'Possession', 'When mogui die or time out, they cast your dominate spell on an enemy within dominate range, from the mogui.', [Tags.Enchantment])

	def get_extra_examine_tooltips(self):
		return [Mogui(), self.spell_upgrades[0], self.spell_upgrades[1], self.spell_upgrades[2]]

	def get_description(self):
		return ("Summon a mogui, a rain demon which creates another mogui if it's soaked or in a Rain Cloud. This effect destroys these clouds.\n"
				"Mogui have [{minion_health}_HP:minion_health], and a melee attack which deals [{minion_damage}_physical:physical] damage. "
				"Mogui, and their copies, vanish after [{minion_duration}_turns:minion_duration].").format(**self.fmt_dict())

	def make_mogui(self, turns):
		unit = Mogui()
		unit.max_hp = self.get_stat('minion_health')
		unit.turns_to_death = turns
		unit.source = self
		unit.apply_buff(MoguiSplitting(self))
		if self.get_stat('cold'):
			grant_minion_spell(Icicle, unit, self.caster, cool_down=8)
		if self.get_stat('claws'):
			leap = LeapAttack(damage=self.get_stat('minion_damage'),damage_type=Tags.Lightning,range=self.get_stat('minion_range',base=4),is_leap=True)
			leap.name = "Leaping Claws"
			unit.spells.append(leap)
		return unit

	def cast_instant(self, x, y):
		unit = self.make_mogui(self.get_stat('minion_duration'))
		apply_minion_bonuses(self, unit)
		self.owner.level.summon(self.owner, unit, target=Point(x, y), team=self.owner.team)



class MitreMovement(Spell):
	def on_init(self):
		self.name = "Mitre Movement" ##This spell's goal will be pretty obvious: move like a bishop.
		self.level = 3
		self.tags = [Tags.Holy, Tags.Sorcery, Tags.Translocation]
		self.asset =  ["TcrsCustomModpack", "Icons", "bishop_movement"]
		self.description = "Teleport to target tile in a diagonal line."

		self.max_charges = 12
		self.range = 99
	
		self.upgrades[('scourge','num_targets')] = ([1,2], 4, "Scourging", "Cast your scourge spell on [2:num_targets] random unit in line of sight from the starting point.")
		self.upgrades['requires_los'] = (-1, 2, "Blindcasting", "This spell can be cast without line of sight")
		self.upgrades['blast'] = (1, 4, "Dramatic Entrance", "Deal 5 holy damage to all targets in line of sight. This damage is fixed.")
		

	def can_cast(self, x, y):
		return Spell.can_cast(self, x, y) and self.caster.level.can_move(self.caster, x, y, teleport=True) and Point(x,y) in self.get_targetable_tiles()

	def get_targetable_tiles(self):
		tiles = []
		size = self.get_stat('range')
		x = self.caster.x
		y = self.caster.y
		def get_diagonal_line(size, x_mult, y_mult):
			for i in range(size):
				p = Point(x+i*x_mult, y+i*y_mult)
				if not self.caster.level.is_point_in_bounds(p):
					break
				if self.caster.level.tiles[p.x][p.y].is_wall():
					if self.caster.level.can_walk(p.x, p.y):
						tiles.append(p)
					elif self.get_stat('requires_los'):
						break
					else:
						continue
				if self.caster.level.tiles[p.x][p.y].is_chasm:
					if self.caster.level.can_walk(p.x, p.y):
						tiles.append(p)
				else:
					tiles.append(p)
		get_diagonal_line(size, 1, 1)
		get_diagonal_line(size, -1 , 1)
		get_diagonal_line(size, 1 , -1)
		get_diagonal_line(size, -1 , -1)
		return tiles

	def cast(self, x, y):
		start = Point(self.caster.x, self.caster.y)
		self.caster.level.show_effect(self.caster.x, self.caster.y, Tags.Translocation)
		yield self.caster.level.act_move(self.caster, x, y, teleport=True)
		if self.get_stat('blast'):
			units = [u for u in self.caster.level.units if are_hostile(u, self.caster) and self.owner.level.can_see(self.caster.x, self.caster.y, u.x, u.y)]
			for u in units:
				u.deal_damage(5, Tags.Holy, self)
		if self.get_stat('scourge'):
			units = [u for u in self.caster.level.units if are_hostile(u, self.caster) and self.owner.level.can_see(start.x, start.y, u.x, u.y)]
			for i in range(self.get_stat('num_targets',base=2)):
				if units != []:
					unit = random.choice(units)
					units.remove(unit)
					spell = self.caster.get_or_make_spell(ScourgeSpell)
					self.caster.level.act_cast(self.caster, spell, unit.x, unit.y, pay_costs=False)



def Hydra():
	unit = Snake()
	unit.name = "Lernaean Hydra"
	unit.asset = ["TcrsCustomModpack", "Units", "hydra"]
	unit.max_hp = 54
	unit.spells[0].damage = 18
	unit.buffs.append(SpawnOnDeath(TwoHeadedSnake, 3))
	return unit

class LoadedDice(Buff):
	def __init__(self, roll):
		self.roll = roll
		Buff.__init__(self)
		self.name = "Loaded Dice: " + str(roll)
		self.color = Tags.Chaos.color
		self.description = "Always roll at least a " + str(roll) + " or higher."

class ChaosDice(Spell):
	def on_init(self):
		self.name = "Chaotic Ice Dice"
		self.tags = [Tags.Ice, Tags.Chaos, Tags.Sorcery]
		self.asset =  ["TcrsCustomModpack", "Icons", "ice_dice"]
		self.level = 4
		
		self.max_charges = 6
		self.damage = 10
		self.damage_type = [Tags.Physical, Tags.Fire, Tags.Lightning, Tags.Ice]
		self.range = 0
		
		self.self_target = True
		
		self.upgrades['ice'] = (1, 2, "Pure Ice Dice", "Instead of dealing damage, cast your Iceball, Freeze, Deathchill, and Cold Machination spells randomly on the targets.")
		self.upgrades[('loaded','num_targets')] = ([1,6], 4, "Loaded Dice", "Each roll is at least 1 value higher than the previous roll, until you hit the max roll. Your max roll is now equivalent to your num targets.")
		self.upgrades['snake'] = (1, 4, "Snake Eyes", "Roll two times, adding up the total. Each '1' rolled summons a lernaean hydra.", [Tags.Nature, Tags.Conjuration])

	def get_description(self):
		return ("Roll a number between 1 to 6. Deal [{damage}_damage:damage] multiplied by X, to X random enemies where X is the number rolled. \n"
				" The damage is chosen from one of: [Fire], [Lightning], [Ice], and [Physical]. The same enemy is never targeted twice.").format(**self.fmt_dict())

	def get_extra_examine_tooltips(self):
		return [self.spell_upgrades[0], self.spell_upgrades[1], self.spell_upgrades[2], Hydra()]

	def cast(self, x, y):
		if self.get_stat('loaded'):
			upper = self.get_stat('num_targets',base=6)
			roll = random.randint(1, upper)
		else:
			roll = random.randint(1,6)
		if self.get_stat('loaded'):
			buff = self.caster.get_buff(LoadedDice)
			if not buff and roll < upper:
				self.caster.apply_buff(LoadedDice(roll))
			elif roll == upper:
				pass  
			else:
				roll = random.randint(buff.roll + 1, upper)
				if roll == upper:
					self.caster.remove_buff(buff)
				else:
					buff.roll = roll
					buff.name = "Loaded Dice: " + str(roll)
					buff.description = "Always roll at least a " + str(roll) + " or higher."

		if self.get_stat('snake'):
			roll_snake = random.randint(1,6)
			count = 0
			if roll == 6:
				count += 1
			if roll_snake == 1:
				count += 1
			for i in range(count):
				unit = Hydra()
				apply_minion_bonuses(self, unit)
				self.summon(unit, Point(self.caster.x, self.caster.y))
			roll += roll_snake

		cur_targets = []
		for i in range(roll):
			all_targets = [u for u in self.caster.level.units if self.caster.level.are_hostile(self.caster, u) and u not in cur_targets]
			if not all_targets:
				return
			target = random.choice(all_targets)
			all_targets.remove(target)
			cur_targets.append(target)
			
			if self.get_stat('ice'):
				rand_spell = random.choice([Iceball, Freeze, DeathChill, Machination])
				spell = self.caster.get_or_make_spell(rand_spell)
				self.caster.level.act_cast(self.caster, spell, target.x, target.y, pay_costs=False)
				self.caster.level.show_path_effect(self.owner, target, Tags.Ice, minor=True)
			else:
				dtype = random.choice([Tags.Fire, Tags.Lightning, Tags.Physical, Tags.Ice])
				target.deal_damage(self.get_stat('damage') * roll, dtype, self)
				self.owner.level.show_path_effect(self.owner, target, dtype, minor=True)
		yield



class SanguineThirst(Buff):
	def __init__(self, spell):
		Buff.__init__(self)
		self.spell = spell
		self.name = "Wraith Hunger"
		self.buff_type = BUFF_TYPE_BLESS
		self.stack_type = STACK_INTENSITY
		self.asset = ["status", "blood_tap"] ##TODO make an asset
		self.tag_bonuses_pct[Tags.Blood]['hp_cost'] = 50
		if self.spell.get_stat('wrath'):
			self.tag_bonuses_pct[Tags.Blood]['damage'] = 50

class WraithHunger(Spell):
	def on_init(self):
		self.name = "Wraith's Hunger"
		self.asset = ["TcrsCustomModpack", "Icons", "wraith_hunger"]
		self.tags = [Tags.Arcane, Tags.Sorcery, Tags.Blood]
		self.level = 2
		
		self.hp_cost = 2
		self.damage = 30
		self.damage_type = [Tags.Arcane]
		self.range = 5

		self.upgrades['rift'] = (1, 3, "Rift Wraith", "If there is no unit to target, summon a void rift at target tile for 30 turns.", [Tags.Conjuration])
		self.upgrades['drake'] = (1, 6, "Drake Portal", "If you kill the target, pay 15 hp to cast your Void Drake on its tile. This counts as spending hp.", [Tags.Dragon])
		self.upgrades['wrath'] = (1, 2, "Wraith's Wrath", "The debuff also grants blood spells 50% bonus damage.", [Tags.Enchantment])
		
	def get_description(self):
		return "Deal [{damage}_Arcane:Arcane] damage. If no target was killed, increase the health cost of your blood spells by 50% for 8 turns. This debuff can stack.".format(**self.fmt_dict())

	def get_extra_examine_tooltips(self):
		return [self.spell_upgrades[0], VoidSpawner(), self.spell_upgrades[1], VoidDrake(), self.spell_upgrades[2]]

	def cast_instant(self, x, y):
		unit = self.caster.level.get_unit_at(x, y)
		if unit:
			unit.deal_damage(self.get_stat('damage'), Tags.Arcane, self)
			if unit.is_alive():
				self.caster.apply_buff(SanguineThirst(self), 7)
			elif self.get_stat('drake') and self.caster.cur_hp > 15:
				self.caster.cur_hp -= 15
				self.caster.level.event_manager.raise_event(EventOnSpendHP(self.caster, 15), self.caster)
				spell = self.caster.get_or_make_spell(SummonVoidDrakeSpell)
				self.caster.level.act_cast(self.caster, spell, x, y, pay_costs=False)
		elif not unit and self.get_stat('rift'):
			u = VoidSpawner()
			u.turns_to_death = 30
			apply_minion_bonuses(self, u)
			self.summon(unit=u, target=Point(x,y))
			self.caster.apply_buff(SanguineThirst(self), 7)
		else:
			self.caster.apply_buff(SanguineThirst(self), 7)



class Landmine_Prop(Prop):
	def __init__(self, owner):
		self.name = "Mine"
		self.asset = ["TcrsCustomModpack", "Tiles", "landmine"]
		self.damage = 15
		self.damage_type = Tags.Physical
		self.owner = owner
		self.source = None
		self.radius = 1
		self.spell = None

	def get_impacted_tiles(self, x, y):
		return [p for stage in Burst(self.owner.level, Point(x, y), self.radius) for p in stage]

	def on_unit_enter(self, unit):
		if not are_hostile(self.owner, unit):
			return
		if self.source.get_stat('shrapnel'):
			rad = 2
		else:
			rad = 1
		for t in self.owner.level.get_points_in_rect(unit.x-rad, unit.y-rad, unit.x+rad, unit.y+rad):
			self.owner.level.deal_damage(t.x, t.y, self.damage, self.damage_type, self)
			if self.source:
				if self.source.get_stat('sword'):
					self.owner.level.deal_damage(t.x, t.y, self.damage, Tags.Arcane, self)
		if self.source:
			if self.source.get_stat('sword'):
				sword = DancingBlade()
				apply_minion_bonuses(self.source, sword)
				self.source.summon(sword, unit)
		if self.spell:
			self.owner.level.act_cast(self.owner, self.spell, unit.x, unit.y, pay_costs=False)
		self.level.remove_obj(self)

class Landmines_Minefield(Upgrade): ##TODO rework this into a skill? It's cool but not particularly good. Maybe make it a hostile realm effect
	def on_init(self):
		self.name = "Recycled Minefield"
		self.level = 2
		self.description = "When a [metallic], [construct], or [glass] unit dies place a landmine on its tile.\nWhen you enter the realm place 30 random mines." ##TODO make these separate upgrades?

		self.owner_triggers[EventOnUnitAdded] = self.on_enter
		self.global_triggers[EventOnDeath] = self.on_death

	def on_enter(self, evt):
		tiles = [t for t in self.owner.level.iter_tiles() if t.is_floor() and not t.prop]
		random.shuffle(tiles)
		for i in range(30):
			spell = self.owner.get_or_make_spell(Landmines)
			prop = spell.make_mine(self.owner)
			self.owner.level.add_obj(prop, tiles[i].x, tiles[i].y) ##TODO TEST on maps with no walking spots.
	
	def on_death(self, evt):
		if Tags.Construct not in evt.unit.tags and Tags.Glass not in evt.unit.tags and Tags.Metallic not in evt.unit.tags:
			return
		tile = self.owner.level.tiles[evt.unit.x][evt.unit.y]
		if tile.is_chasm or tile.prop:
			return
		point = Point(evt.unit.x, evt.unit.y)
		spell = self.owner.get_or_make_spell(Landmines)
		prop = spell.make_mine(self.owner)
		self.owner.level.add_obj(prop, point.x, point.y)

class Landmines(Spell):
	def on_init(self):
		self.name = "Proximity Mine"
		self.level = 2
		self.asset = ["TcrsCustomModpack", "Icons", "landmine_icon"]
		self.tags = [Tags.Sorcery, Tags.Enchantment, Tags.Metallic]

		self.max_charges = 30
		self.damage = 20
		self.damage_type = [Tags.Physical]
		self.range = 99
		
		self.quick_cast = True
		self.must_target_walkable = True

		self.upgrades['sword'] = (1, 3, "Claymore", "Mines deal [arcane] damage as well. After exploding summon a dancing blade.", [Tags.Arcane, Tags.Conjuration])
		self.upgrades['bounce'] = (1, 3, "Bouncing", "After exploding, you cast your metal shard spell on a triggered mine.")
		self.upgrades['shrapnel'] = (1, 4, "Fragmentation", "Mines explode in a 5x5 square. After exploding, you cast your shrapnel blast spell on a triggered mine.", [Tags.Fire])

	def get_extra_examine_tooltips(self):
		return [self.spell_upgrades[0], DancingBlade(), self.spell_upgrades[1], self.spell_upgrades[2]]

	def get_description(self):
		return ("Place a mine on target tile. It detonates when a hostile unit moves onto it, dealing [{damage}_physical:physical] in a 3x3 square."
				"\nThis spell can be cast once without ending your turn.").format(**self.fmt_dict())

	def can_cast(self, x, y):
		tile = self.caster.level.tiles[x][y]
		return not tile.prop and Spell.can_cast(self, x, y)

	def make_mine(self, caster):
		prop = Landmine_Prop(caster)
		prop.source = self
		prop.damage = self.get_stat('damage')
		if self.get_stat('shrapnel'):
			prop.spell = caster.get_or_make_spell(ShrapnelBlast)
		elif self.get_stat('bounce'):
			prop.spell = caster.get_or_make_spell(MetalShard)
		return prop

	def cast_instant(self, x, y):
		prop = self.make_mine(self.caster)
		self.caster.level.add_obj(prop, x, y)



class SeaWyrmBreath(BreathWeapon):
	def __init__(self, spell=None):
		BreathWeapon.__init__(self)
		if spell != None:
			self.spell = spell
		else:
			self.spell = None
		self.name = "Poisonous Breath"
		self.damage = 10
		self.duration = 5
		self.damage_type = Tags.Poison
		self.cool_down = 3
		self.range = 5
		self.angle = math.pi / 6.0

	def get_description(self):
		return "Applies 5 turns of poison"

	def per_square_effect(self, x, y):
		if self.spell != None:
			if self.spell.get_stat('gaseous'):
				cloud = self.spell.owner.get_or_make_spell(PoisonousGas).make_cloud(self.caster)
				self.caster.level.add_obj(cloud, x, y)
			if self.spell.get_stat('rainy'):
				rain_storm = self.spell.owner.get_or_make_spell(RainStormSpell)
				cloud = RainCloud(self.spell.owner, spell=rain_storm)
				cloud.duration = rain_storm.get_stat('duration')
				self.caster.level.add_obj(cloud, x, y)
			
		unit = self.caster.level.get_unit_at(x, y)
		if unit:
			self.caster.level.deal_damage(x, y, self.get_stat('damage'), self.damage_type, self)
			unit.apply_buff(Poison(), self.get_stat('duration'))
		else:
			self.caster.level.deal_damage(x, y, 0, self.damage_type, self)

def SeaSerpent_Unit(s=None):
	unit = Unit()
	unit.name = "Sea Serpent"
	unit.asset = ["TcrsCustomModpack", "Units", "sea_serpent_unit"]
	unit.max_hp = 75

	if s != None:
		unit.spells.append(SeaWyrmBreath(s))
	else:
		unit.spells.append(SeaWyrmBreath())
	unit.spells.append(SimpleMeleeAttack(14, trample=True))

	unit.tags = [Tags.Nature, Tags.Dragon, Tags.Living]
	if water_tag in Knowledges:
		unit.tags.append(Tags.Water)

	unit.resists[Tags.Poison] = 100
	unit.resists[Tags.Lightning] = -100
	unit.resists[Tags.Ice] = -100
	return unit

class SeaSerpent(Spell):
	def on_init(self):
		self.name = "Sea Serpent"
		self.tags = [Tags.Nature, Tags.Conjuration, Tags.Dragon]
		self.level = 5
		self.asset = ["TcrsCustomModpack", "Icons", "sea_serpent_icon"]
		
		self.max_charges = 2
		self.range = 5
		self.minion_health = 75
		self.minion_damage = 14
		self.minion_range = 7

		self.must_target_empty = True
		self.must_target_walkable = True

		if water_tag in Knowledges:
			self.tags.append(Tags.Water)
			
		self.upgrades['rainy'] = (1, 2, "Rain Clouds", "The breath weapon also creates your rain storm clouds on each tile.")
		self.upgrades['gaseous'] = (1, 4, "Poison Clouds", "The breath weapon also creates your poisonous gas clouds on each tile.")
		self.upgrades['abc'] = (1, 4, "ABC Serpent", "The serpent gains 5 max hp, 1 breath damage, and 2 melee damage for each unique letter in the names of spells the caster knows.")

	def get_description(self):
		return ("Summon a Sea Serpent at target square.\n Sea Serpents have [{minion_health}_HP:minion_health], 100 [poison] resistance, and -100 [Ice] and [Lightning] resistances.\n"
				"They have a breath weapon which deals [{minion_damage}_poison:poison] damage and poisons for 5 turns, "
				"and a trampling melee attack which deals [{minion_damage}_physical:physical] damage.").format(**self.fmt_dict())
	
	def get_extra_examine_tooltips(self):
		return [self.wyrm(), self.spell_upgrades[0], self.spell_upgrades[1], self.spell_upgrades[2]]

	def wyrm(self):
		wyrm = SeaSerpent_Unit(self)
		apply_minion_bonuses(self, wyrm)
		#wyrm.max_hp = self.get_stat('minion_health')
		#wyrm.spells[0].damage = self.get_stat('breath_damage')
		#wyrm.spells[0].range = self.get_stat('minion_range')
		#wyrm.spells[1].damage = self.get_stat('minion_damage')
		if self.get_stat('abc'):
			alphabet = {}
			for s in self.caster.spells:
				for letter in s.name:
					if letter.lower() not in [' ', '\'', '%', ':']:
						alphabet[letter] = True
			#print(alphabet.items())
			num_letters = len(alphabet)
			wyrm.max_hp += num_letters * 5
			wyrm.spells[0].damage += num_letters
			wyrm.spells[1].damage += num_letters * 2
		return wyrm

	def cast_instant(self, x ,y):
		unit = self.wyrm()
		self.summon(unit, Point(x, y))



class ChannelExtension(Buff):
	def __init__(self, spell):
		Buff.__init__(self)
		self.spell = spell
		if self.spell.get_stat('num_upgrade'):
			self.global_bonuses['num_summons'] = 1
			self.global_bonuses['num_targets'] = 1
			self.global_bonuses['shot_cooldown'] = -1

	def on_init(self):
		self.name = "Channeling Extension"
		self.description = "Every 2 turns the duration of your channeling buff is extended by 1 turn."
		self.bit = True
		self.count = 4

	def on_advance(self):
		self.count -= 1
		if self.count <= 0 and self.spell.get_stat('angels'):
			self.count = 4
			spell = self.spell.owner.get_or_make_spell(AngelicChorus)
			unit = spell.angel()
			if spell.get_stat('cast_deathbolt'):
				grant_minion_spell(DeathBolt, unit, self.owner, cool_down=4)
			self.spell.summon(unit, self.owner)
			
		channel_buff = self.owner.get_buff(ChannelBuff)
		if not channel_buff:
			return
		if channel_buff.turns_left > 1 and self.bit:
			channel_buff.turns_left += 1
			self.bit = False
		else:
			self.bit = True
		if self.spell.get_stat('crystals'):
			self.owner.level.queue_spell(self.spell.crystal())

class ChannelPylonProp(Prop):
	def __init__(self, spell):
		self.spell = spell
		self.name = "Channeling Pylon"
		self.description = None
		self.asset = ["TcrsCustomModpack", "Misc", "channel_pylon3"] ##Variant of Mystic Shrine from RW1. Props to K.Hoops

	def get_description(self):
		return "Standing here causes your channeling to decrease only every second turn."

	def advance(self):
		pass

	def on_player_enter(self, player):
		player.apply_buff(ChannelExtension(self.spell))

	def on_player_exit(self, player):
		player.remove_buffs(ChannelExtension)

class ChannelPylonSpell(Spell):
	def on_init(self):
		self.name = "Channeling Pylon"
		self.tags = [Tags.Arcane, Tags.Enchantment]
		self.level = 3
		self.asset = ["TcrsCustomModpack", "Icons", "channel_pylon_icon"]
		self.description = "Place a channeling pylon at target tile.\nWhile standing on the pylon your channeling buff lasts twice as long."
		
		self.max_charges = 3
		self.range = 3
		
		self.must_target_empty = True
		self.must_target_walkable = True
		
		self.upgrades[('crystals','damage')] = ([1,8], 2, "Crystal Pylon", "Every turn spent channeling on the pylon also deals [8_ice:ice] damage to a random enemy in line of sight, and [8_arcane:arcane] damage to another.", [Tags.Ice])
		self.upgrades['angels'] = (1, 1, "Angelic Beacon", "For every 4 turns spent continuously on the pylon, summon an angelic singer from your choir of angels spell.", [Tags.Holy])
		self.upgrades['num_upgrade'] = (1, 3, "Booster", "The pylon buff grants you +1 num summons, +1 num targets, and -1 shot cooldown.")
	
	def can_cast(self, x, y):
		tile = self.caster.level.tiles[x][y]
		return not tile.prop and Spell.can_cast(self, x, y)

	def cast(self, x, y):
		prop = ChannelPylonProp(self)
		self.owner.level.add_prop(prop, x, y)
		yield

	def crystal(self):
		candidates = [u for u in self.owner.level.get_units_in_los(self.owner) if are_hostile(self.owner, u)]
		random.shuffle(candidates)
		if not candidates:
			return

		target = candidates.pop()
		self.owner.level.show_beam(self.owner, target, Tags.Ice)
		target.deal_damage(self.get_stat('damage',base=8), Tags.Ice, self)
		if candidates == []:
			return
		
		target2 = candidates.pop()
		self.owner.level.show_beam(self.owner, target2, Tags.Arcane)
		target2.deal_damage(self.get_stat('damage',base=8), Tags.Arcane, self)
		yield



class AnnointedBuff(Buff):
	def __init__(self, spell):
		self.spell = spell
		Buff.__init__(self)

	def on_init(self):
		self.buff_type = BUFF_TYPE_CURSE
		self.name = "Annointed"
		self.asset = ["TcrsCustomModpack", "Misc", "annointed_buff"]
		self.color = Tags.Holy.color
		self.owner_triggers[EventOnDeath] = self.on_death

	def on_death(self, evt):
		if self.spell.get_stat('lamasu') and random.randint(0,1) == 1:
			unit = Lamasu()
			apply_minion_bonuses(self, unit)
			unit.turns_to_death = None
		else:
			unit = self.spell.make_knight()
		self.spell.summon(unit, target=self.owner)

class SacrificialAltarProp(Prop):
	def __init__(self, spell):
		self.spell = spell
		self.name = "Sacrificial Altar"
		self.description = None
		self.asset = ["TcrsCustomModpack", "Misc", "sacrifice_altar2"]
		self.count = 0

	def get_description(self):
		return "Units which pass through are annointed, summoning temporary twilight knights upon death."
	
	def on_unit_enter(self, unit):
		if unit.is_player_controlled:
			return
		if unit.turns_to_death != None:
			return
		unit.apply_buff(AnnointedBuff(self.spell),self.spell.get_stat('duration'))
		if self.spell.get_stat('deathtouch') and self.count == 0:
			spell = self.spell.owner.get_or_make_spell(TouchOfDeath)
			self.spell.owner.level.act_cast(self.spell.owner, spell, unit.x, unit.y, pay_costs=False)
			self.count = 7
			
	def advance(self):
		if self.count > 0:
			self.count -= 1

class SacrificialAltarSpell(Spell):
	def on_init(self):
		self.name = "Altar of Sacrifice"
		self.tags = [Tags.Dark, Tags.Holy, Tags.Conjuration, Tags.Enchantment]
		self.level = 4
		self.asset = ["TcrsCustomModpack", "Icons", "sacrifice_altar_icon"]
		
		self.max_charges = 2
		self.range = 5
		self.duration = 12
		self.minion_health = 195
		self.minion_damage = 14
		self.minion_duration = 4
		
		self.must_target_empty = True
		self.must_target_walkable = True
		
		self.upgrades['lamasu'] = (1 , 6, "Sacred Bull", "Gain a 25% chance to summon a lamasu, which does not expire but does not reincarnate.") ##TODO incorporate chance
		self.upgrades['revives'] = (1, 4, "Revivalism", "The twilight knight gain 2 more reincarnations.")
		self.upgrades['deathtouch'] = (1, 5, "Altar of Evil", "You cast your touch of death on any unit, except you, which enters the altar. This effect has a 7 turn cooldown.", [Tags.Sorcery])
	
	def get_description(self):
		return ("Place a sacrificial altar at target tile.\nEach permanent unit that moves onto it, gains the annointed debuff which summons a twilight knight when the unit dies.\n"
				"Annointed lasts [{duration}_turns:duration] turns, twilight knights last for [{minion_duration}_turns:minion_duration] turns, and reincarnate once.").format(**self.fmt_dict())
	
	def get_extra_examine_tooltips(self):
		return [self.make_knight(), self.spell_upgrades[0], Lamasu(), self.spell_upgrades[1], self.spell_upgrades[2]]

	def can_cast(self, x, y):
		tile = self.caster.level.tiles[x][y]
		return not tile.prop and Spell.can_cast(self, x, y)

	def make_knight(self):
		knight = TwilightKnight()
		apply_minion_bonuses(self, knight)
		if self.get_stat('revives'):
			buff = knight.get_buff(ReincarnationBuff)
			buff.lives += 2
		return knight

	def cast(self, x, y):
		prop = SacrificialAltarProp(self)
		self.owner.level.add_prop(prop, x, y)
		yield



class BloodRefundRegen(Buff):
	def __init__(self, amount):
		Buff.__init__(self)
		self.amount = amount

	def on_init(self):
		self.color = Tags.Blood.color
		self.name = "Regeneration"
		self.description = "Regenerating HP"
		self.buff_type = BUFF_TYPE_BLESS
		self.stack_type = STACK_INTENSITY

	def on_advance(self):
		if self.amount > 5:
			heal_amount = 5
		else:
			heal_amount = self.amount
		self.amount -= heal_amount
		self.owner.deal_damage(-heal_amount, Tags.Heal, self)
		if self.amount <= 0:
			self.owner.remove_buff(self)

class BloodRefundCircle(Buff):
	def on_init(self):
		self.color = Tags.Blood.color
		self.name = "Refund"
		self.description = "Gain a stacking regeneration buff equal to 50% of the hp cost of your blood spells, rounded down. The buff heals up to 5 hp a turn."
		self.owner_triggers[EventOnSpellCast] = self.on_cast

	def on_cast(self, evt):
		if not evt.pay_costs:
			return
		if Tags.Blood in evt.spell.tags and evt.spell.hp_cost:
			half = evt.spell.hp_cost // 2
			self.owner.apply_buff(BloodRefundRegen(half))

class CircleofBlood(Prop):
	def __init__(self, spell, x, y):
		self.spell = spell
		self.point = Point(x, y)
		self.name = "Ritual Circle"
		self.asset = ["TcrsCustomModpack", "Misc", "ritual_circle"]
		self.description = "Summons 20 hemogloblins. When it runs out, summon a blood bear."
		self.count = self.spell.get_stat('num_summons')
		self.bit = True

	def advance(self):
		if not self.bit:
			self.bit = True
			return
		self.bit = False
		self.count -= 1
		unit = hemogloblin()
		apply_minion_bonuses(self.spell, unit)
		self.spell.summon(unit, self.point)
		self.description = "Summons " + str(self.count) + " hemogloblins. When it runs out, summon a blood bear."
		
		if self.count == 0:
			bear = BloodBear()
			apply_minion_bonuses(self.spell, bear)
			self.spell.summon(bear, self.point)
			bear.turns_to_death = None
			if self.spell.get_stat('complete'):
				spell = self.spell.owner.get_or_make_spell(FleshFiendSpell)
				self.spell.owner.level.act_cast(self.spell.owner, spell, self.point.x, self.point.y, pay_costs=False)
			self.spell.owner.level.remove_prop(self)

	def on_player_enter(self, player):
		if self.spell.get_stat('refund'):
			player.apply_buff(BloodRefundCircle())

	def on_player_exit(self, player):
		if self.spell.get_stat('refund'):
			player.remove_buffs(BloodRefundCircle)

def hemogloblin():
	unit = Goblin()
	unit.asset = ["TcrsCustomModpack", "Units", "goblin_hemoglobin"]
	unit.tags.append(Tags.Blood)
	return unit

class SpillBlood(Upgrade):
	def on_init(self):
		self.level = 1
		self.name = "Spilled Blood"
		self.description = "The first time in each realm you take 40 total damage, you cast your ritual circle for free at your tile, or an adjacent tile if your tile is unavailable."
		self.owner_triggers[EventOnDamaged] = self.on_dmg
		self.owner_triggers[EventOnUnitAdded] = self.on_enter
		self.count = 40

	def on_enter(self, evt):
		self.count = 40

	def on_dmg(self, evt):
		if self.count <= 0:
			return
		self.count -= evt.damage
		point = Point(self.owner.x, self.owner.y)
		adj_point = None
		tile = self.owner.level.tiles[point.x][point.y]
		if tile.prop:
			rect = list(self.owner.level.get_points_in_rect(point.x - 1, point.y - 1, point.x + 1, point.y + 1))
			random.shuffle(rect)
			for p in rect:
				t = self.owner.level.tiles[p.x][p.y]
				if not t.prop and t.can_walk:
					adj_point = Point(p.x, p.y)
					break
		if adj_point != None:
			point = adj_point
			
		if self.count <= 0:
			spell = self.owner.get_or_make_spell(RitualCircle)
			self.owner.level.act_cast(self.owner, spell, point.x, point.y, pay_costs=False)

class RitualCircle(Spell):
	def on_init(self):
		self.name = "Ritual Circle"
		self.tags = [Tags.Blood, Tags.Conjuration, Tags.Enchantment]
		self.level = 2
		self.asset = ["TcrsCustomModpack", "Icons", "ritual_circle_icon"]

		self.hp_cost = 20
		self.max_charges = 1
		self.range = 1.5
		self.minion_duration = 15
		self.minion_health = 7
		self.minion_damage = 2
		self.num_summons = 20

		self.melee = True
		self.must_target_empty = True
		self.must_target_walkable = True
	
		self.add_upgrade(SpillBlood())
		self.upgrades['complete'] = (1, 5, "Complete the Ritual", "When the circle expires, also cast your flesh fiend at the circle.")
		self.upgrades['refund'] = (1, 4, "Refund", "When you are standing in your blood circle, you regenerate 50% of the hp costs of your blood spells over 5 turns.")

	def get_description(self):
		return ("Draw a circle of blood in an adjacent tile. Every 2 turns it summons a hemogloblin which lasts [{minion_duration}_turns:minion_duration]."
				"Summons up to [{num_summons}_globlins:num_summons]. When the circle expires it summons a blood bear.").format(**self.fmt_dict())

	def get_extra_examine_tooltips(self):
		return [hemogloblin(), BloodBear()] + self.spell_upgrades

	def can_cast(self, x, y):
		tile = self.caster.level.tiles[x][y]
		return not tile.prop and Spell.can_cast(self, x, y) ##Unlikely to end up on walls, but I think icy veins could actually place it on an adjacent wall.

	def cast(self, x, y):
		prop = CircleofBlood(self, x, y)
		self.owner.level.add_prop(prop, x, y)
		yield



class HarnessRainbow(Upgrade):
	def on_init(self):
		self.level = 3
		self.name = "The Excellent Prismatic Spray"
		self.description = "For each different damage type which killed a unit from any source, the next preparation takes 3 fewer turns, to a minimum of 1. Resets upon cast."
		self.global_triggers[EventOnDeath] = self.on_death
		self.owner_triggers[EventOnSpellCast] = self.on_cast
		self.dtypes = []

	def on_death(self, evt):
		if evt.damage_event == None:
			return
		dtype = evt.damage_event.damage_type
		if not dtype:
			return
		if dtype not in self.dtypes:
			self.dtypes.append(dtype)
		buff = self.owner.get_buff(PrismaticQuickness)
		if not buff:
			buff = PrismaticQuickness()
			self.owner.apply_buff(PrismaticQuickness())
		buff.count = len(self.dtypes)
		buff.name = "Prismatic Quickness: " + str(buff.count)
		buff.description = "Prepare Vance's Rainbow " + str(buff.count * 3) +" turns faster"
		
	def on_cast(self, evt):
		if not type(evt.spell) == type(PrismaticSpray()):
			return
		self.dtypes = []

class PrismaticQuickness(Buff):
	def on_init(self):
		self.name = "Prismatic Excellence"
		self.description = "Prepare Vance's Rainbow faster."
		self.count = 0

class PrismaticSpray(Spell): ##Very clearly inspired by Jack Vance's Dying Earth
	def on_init(self):
		self.name = "Vance's Rainbow"
		self.tags = [Tags.Arcane, Tags.Sorcery]
		self.level = 3
		self.asset = ["TcrsCustomModpack", "Icons", "vance_rainbow"]
		
		self.max_charges = 10
		self.damage = 40
		self.damage_type = [Tags.Fire, Tags.Lightning, Tags.Physical, Tags.Ice, Tags.Dark, Tags.Arcane, Tags.Holy, Tags.Poison]
		self.range = 30
		self.num_targets = 10
		
		self.angle = math.pi / 5.0
		self.can_target_self = False
		self.requires_los = False
		self.prepared = True
		
		self.add_upgrade(HarnessRainbow())
		self.upgrades['cloak'] = (1, 2, "Alamer's Cloak", "Gain a random 2 damage aura which deals 2 of the damage types, has a radius of [5:radius], and last [25:duration] turns.", [Tags.Enchantment])
		self.upgrades[('prismatic','duration')] = (1, 1, "The Kaleidoscopic Spray", "Blind every unit on the map for a [1:duration] turn upon casting.", [Tags.Holy])

	def get_description(self):
		return ("This spell must be prepared after each cast, stunning you for 20 turns. Preparation lasts between realms.\n"
				"Shoot [{num_targets}:num_targets] beams at random tiles in a cone. Each beam deals [{damage}_:damage] damage of a random type, then converges on the target point.").format(**self.fmt_dict())

	def get_extra_examine_tooltips(self):
		return self.spell_upgrades

	def aoe(self, x, y):
		target = Point(x, y)
		return Burst(self.caster.level, Point(self.caster.x, self.caster.y), self.get_stat('range'), 
						burst_cone_params=BurstConeParams(target, self.angle), ignore_walls=True)

	def get_impacted_tiles(self, x, y):
		if self.prepared:
			return [p for stage in self.aoe(x, y) for p in stage]
		else:
			return [Point(self.caster.x, self.caster.y)]

	def can_cast(self, x, y):
		if self.prepared:
			return Spell.can_cast(self, x, y)
		else:
			return Spell.can_cast(self, x, y) and not (self.caster.has_buff(StunImmune) or self.caster.debuff_immune)

	def cast(self, x, y):
		if not self.prepared:
			self.prepared = True
			turns = 20
			pris_quick = self.owner.get_buff(PrismaticQuickness)
			if pris_quick:
				turns = 20 - (pris_quick.count * 3)
				if turns <= 1:
					turns = 1
				self.caster.remove_buff(pris_quick)
			
			self.caster.apply_buff(Stun(),turns)
		else:
			self.prepared = False
			all_points = []
			start = Point(self.caster.x, self.caster.y)
			end = Point(x, y)
			for stage in self.aoe(x, y):
				for point in stage:
						all_points.append(point)
			random.shuffle(all_points)

			if self.get_stat('cloak'):
				dtype = random.choice(self.damage_type)
				dtype2 = random.choice(self.damage_type)
				while dtype2 == dtype:
					dtype2 = random.choice(self.damage_type)
				buff = DamageAuraBuff(damage=self.get_stat('aura_damage',base=2), radius=self.get_stat('radius',base=5), damage_type=[dtype, dtype2])
				buff.color = dtype.color
				buff.source = self
				self.caster.apply_buff(buff, self.get_stat('duration',base=25))
				
			if self.get_stat('prismatic'):
				units = list(self.caster.level.units)
				for unit in units:
					unit.apply_buff(BlindBuff(), self.get_stat('duration',base=1))

			for i in range(self.get_stat('num_targets')):
				if len(all_points) > i:
					mid = all_points[i]
				else:
					return
				dtype = random.choice(self.damage_type)
				self.double_bolt(start, mid, end, dtype)
		yield

	def double_bolt(self, start, mid, end, dtype):
		for point in Bolt(self.caster.level, start, mid, two_pass=False, find_clear=False):
			if not self.caster.level.tiles[point.x][point.y].can_see:
				self.caster.level.make_floor(point.x, point.y)
			self.caster.level.deal_damage(point.x, point.y, self.get_stat('damage'), dtype, self)
		for point in Bolt(self.caster.level, mid, end, two_pass=False, find_clear=False):
			if not self.caster.level.tiles[point.x][point.y].can_see:
				self.caster.level.make_floor(point.x, point.y)
			self.caster.level.deal_damage(point.x, point.y, self.get_stat('damage'), dtype, self)



class OpalescentEyeBuff(Spells.ElementalEyeBuff):
	def __init__(self, freq, spell):
		Spells.ElementalEyeBuff.__init__(self, Tags.Holy, 0, freq, spell)
		self.name = "Eye of Ao"
		self.color = Tags.Holy.color
		self.asset = ["TcrsCustomModpack", "Misc", "ao_eye"]

	def on_advance(self):
		self.cooldown -= 1
		if self.cooldown <= 0:
			self.cooldown = self.freq
			threshold = self.get_threshold()
			possible_targets = self.owner.level.units
			possible_targets = [t for t in possible_targets if self.owner.level.are_hostile(t, self.owner)]
			if not self.spell.get_stat('penetrate'):
				possible_targets = [t for t in possible_targets if self.owner.level.can_see(t.x, t.y, self.owner.x, self.owner.y)]
			possible_targets = [t for t in possible_targets if t.max_hp <= threshold]

			if possible_targets:
				random.shuffle(possible_targets)
				target = possible_targets.pop(0)
				self.owner.level.queue_spell(self.shoot(Point(target.x, target.y)))
				num_targets = self.spell.get_stat('num_targets',base=3) - 1
				while num_targets > 0 and len(possible_targets) > 0:
					num_targets -= 1
					target = possible_targets.pop(0)
					self.owner.level.queue_spell(self.shoot(Point(target.x, target.y)))

	def get_threshold(self):
		threshold = self.spell.get_stat('damage')
		if self.spell.get_stat('triple'):
			threshold *= 3
		return threshold


	def shoot(self, target):
		self.owner.level.show_effect(0, 0, Tags.Sound_Effect, 'sorcery_ally')
		path = self.owner.level.get_points_in_line(Point(self.owner.x, self.owner.y), target, find_clear=True)

		for point in path:
			self.owner.level.deal_damage(point.x, point.y, 0, Tags.Holy, self.spell)
		self.on_shoot(target)
		yield

	def on_shoot(self, target):
		unit = self.owner.level.get_unit_at(target.x, target.y)
		if not unit:
			return
		unit.team = self.owner.team
		buff = random.choice([Stun(), BlindBuff(), FearBuff()])
		unit.apply_buff(buff, 2)

class OpalescentEyes(Spell): ##Very clearly inspired by Jack Vance's Dying Earth
	def on_init(self):
		self.name = "Ao's Opal Eyes"
		self.tags = [Tags.Holy, Tags.Eye, Tags.Enchantment]
		self.level = 4
		self.asset = ["TcrsCustomModpack", "Icons", "eye_of_ao"]

		self.max_charges = 4		
		self.damage = 40
		self.damage_type = [Tags.Holy] ##Will this ever be required? It's going here in case it interacts with stuff.
		self.duration = 30
		self.range = 0

		self.self_target = True
		self.shot_cooldown = 3
		self.stats.append('shot_cooldown')
		self.prepared = True
		
		self.upgrades['penetrate'] = (1, 4, "Caligarde's Vision", "Affects units through walls.")
		self.upgrades[('hypnotic','num_targets')] = ([1,3], 6, "The Hypnotic Charm", "Affects up to [3:num_targets] units per turn.")
		self.upgrades['triple'] = (1, 4, "The Unfettered Eye", "Now affects enemies with up to three times its damage stat.") ##TODO check

	def get_description(self):
		return ("This spell must be prepared after each cast, stunning you for 20 turns. Preparation lasts between realms.\n"
				"Every [{shot_cooldown}_turns:shot_cooldown], convert 1 random enemy, with less than [{damage}:holy] max hp, in line of sight, scaling with damage. "
				"Blinds, stuns, or fears the unit for 2 turns.\n"
				"The Buff lasts [{duration}_turns:duration] on the wizard, or 3 turns on minions.").format(**self.fmt_dict())

	def get_extra_examine_tooltips(self):
		return self.spell_upgrades

	def can_cast(self, x, y):
		if self.prepared:
			return Spell.can_cast(self, x, y)
		else:
			return Spell.can_cast(self, x, y) and not (self.caster.has_buff(StunImmune) or self.caster.debuff_immune)
		##TODO crashed once while preparing. Perhaps 20 turns is too long? Was doing an eye build to test 

	def cast(self, x, y):
		if not self.prepared:
			self.prepared = True
			self.caster.apply_buff(Stun(),20)
		else:
			self.prepared = False
			buff = OpalescentEyeBuff(self.get_stat('shot_cooldown'), self)
			if self.caster.name == "Wizard":
				duration = self.get_stat('duration')
			else:
				duration = 3
			self.caster.apply_buff(buff, duration)
		yield



class VileMenagerie(Spell): ##Very clearly inspired by Jack Vance's Dying Earth
	def on_init(self):
		self.name = "The Vile Menagerie"
		self.tags = [Tags.Blood, Tags.Chaos, Tags.Conjuration]
		self.level = 5
		self.asset = ["TcrsCustomModpack", "Icons", "vile_menagerie"]

		self.max_charges = 8
		self.hp_cost = 28
		self.range = 0
		self.radius = 5
		self.minion_duration = 18
		self.num_summons = 18

		self.self_target = True
		self.prepared = True
		
		self.upgrades['permanent'] = (1, 5, "Preservation of Pandelume", "Each monster has a 50% to be permanent.") ##Incorporate chance effects
		self.upgrades['chaotic'] = (1, 5, "Leuk-O's Vileness", "Each non-chaos monster has a 25% chance to be chaos touched.")
		self.upgrades['increase'] = (1, 5, "Gestation of Ignoble Servitor", "The monsters are now those ones which could be found in the next realm.")

	def get_description(self):
		return ("This spell must be prepared after each cast, stunning you for 20 turns. Preparation lasts between realms.\n"
				"Summon a random assortment of monsters that could be found in this realm.\n"
				"Summons 18 monsters which last for 18 turns.").format(**self.fmt_dict())

	def get_impacted_tiles(self, x, y):
		if self.prepared:
			return self.caster.level.get_points_in_ball(x, y, self.get_stat('radius'))
		else:
			return [Point(self.caster.x, self.caster.y)]

	def can_cast(self, x, y):
		if self.prepared:
			return Spell.can_cast(self, x, y)
		else:
			return Spell.can_cast(self, x, y) and not (self.caster.has_buff(StunImmune) or self.caster.debuff_immune)

	def cast(self, x, y):
		if not self.prepared:
			self.prepared = True
			self.caster.apply_buff(Stun(),20)
		else:
			self.prepared = False
			if self.get_stat('increase'):
				tier = get_spawn_min_max(self.caster.level.level_no)[1] + 1 ##TODO check to see if this crashes on the highest realms, but it's bounded to 9 so it should be fine.
			else:
				tier = get_spawn_min_max(self.caster.level.level_no)[1]
			if tier > 9:
				tier = 9
			
			for i in range(self.get_stat('num_summons')):
				options = [(s, l) for s, l in spawn_options if l == tier]
				spawner = random.choice(options)[0]
				unit = spawner()
				apply_minion_bonuses(self, unit)
				if self.get_stat('chaotic') and random.random() <= 0.25:
					BossSpawns.apply_modifier(Chaostouched,unit)
				if self.get_stat('permanent') and random.random() <= 0.50:
					unit.turns_to_death = None
				self.summon(unit, Point(x, y), radius=5, sort_dist=False)
		yield



class ShakingConcoction(Buff):
	def __init__(self, spell):
		Buff.__init__(self)
		self.name = "Unstable Mixture"
		self.spell = spell
		self.buff_type = BUFF_TYPE_BLESS
		self.asset = ["TcrsCustomModpack", "Misc", "shaking_concoction"]
		self.stack_type = STACK_REPLACE
		self.owner_triggers[EventOnSpellCast] = self.on_cast
		self.radius_mod = 0
		self.damage_mod = 0
		self.spell_bonuses[UnstableConcoction]['radius'] = 0
		self.cast = False
		
	def on_advance(self):
		if self.cast:
			self.owner.remove_buff(self)
			return
		self.radius_mod += 1
		self.owner.spell_bonuses[UnstableConcoction]['radius'] += 1
		if self.spell.get_stat('danger'):
			self.damage_mod += 4
			self.owner.spell_bonuses[UnstableConcoction]['damage'] += 4
		if self.turns_left == 1:
			self.spell.explode(self.owner.x, self.owner.y, self)

	def on_cast(self, evt):
		if type(evt.spell) == type(UnstableConcoction()):
			self.cast = True

	def on_unapplied(self):
		self.owner.spell_bonuses[UnstableConcoction]['radius'] -= self.radius_mod
		if self.spell.get_stat('danger'):
			self.owner.spell_bonuses[UnstableConcoction]['damage'] -= self.damage_mod

class UnstableConcoction(Spell): ##Very clearly inspired by dota
	def on_init(self):
		self.name = "Unstable Mixture"
		self.tags = [Tags.Nature, Tags.Chaos, Tags.Sorcery, Tags.Enchantment]
		self.level = 3
		self.asset = ["TcrsCustomModpack", "Icons", "unstable_concoction"]
		
		self.max_charges = 16
		self.damage = 10
		self.damage_type = [Tags.Poison, Tags.Physical]
		self.range = 9
		self.radius = 1
		self.duration = 6
		
		self.can_target_self = True
		
		self.upgrades['gaseous'] = (1, 2, "Gaseous Mixture", "Each affected tile has your poisonous gas or dust cloud created on it.")
		self.upgrades['danger'] = (1, 3, "Dangerous Mixture", "The spell gains 4 damage for each turn with the buff.")
		self.upgrades['slime'] = (1, 7, "Slimy Mixture", "A slime drake is summoned at the target tile.", [Tags.Slime])

	def get_description(self):
		return ("Gain Unstable Mixture for [{duration}_turns:duration] turns if you don't have it.\n"
				"If you have the buff, consume it to throw the mixture at target tile, dealing [{damage}_poison:poison] damage and [{damage}_physical:physical] damage in a burst.\n"
				"Each turn with the buff grants the spell +1 radius, but if the buff expires, it explodes on you.").format(**self.fmt_dict())

	def get_extra_examine_tooltips(self):
		return [self.spell_upgrades[0], self.spell_upgrades[1],self.spell_upgrades[2], SlimeDrake()]

	def get_impacted_tiles(self, x, y):
		if not self.caster.has_buff(ShakingConcoction):
			return [Point(self.caster.x, self.caster.y)]
		else:
			return [p for stage in Burst(self.caster.level, Point(x, y), self.get_stat('radius')) for p in stage]

	def cast(self, x, y):
		if not self.caster.has_buff(ShakingConcoction):
			self.caster.apply_buff(ShakingConcoction(self), self.get_stat('duration'))
		else:
			buff = self.caster.get_buff(ShakingConcoction)
			self.explode(x, y, buff)
		yield

	def explode(self, x, y, buff):
		for t in self.get_impacted_tiles(x, y):
			self.caster.level.deal_damage(t.x, t.y, self.get_stat('damage'), Tags.Poison, self)
			self.caster.level.deal_damage(t.x, t.y, self.get_stat('damage'), Tags.Physical, self)
			if self.get_stat('gaseous'):
				if random.random() >= 0.50:
					cloud = self.owner.get_or_make_spell(PoisonousGas).make_cloud(self.owner)
				else:
					cloud = self.owner.get_or_make_spell(AdvancingSandstorm).make_cloud(x, y)
				self.owner.level.add_obj(cloud, t.x, t.y)
		if self.get_stat('slime'):
			unit = SlimeDrake()
			apply_minion_bonuses(self, unit)
			self.summon(unit,Point(x, y))



def SandElemental():
	unit = Unit()
	unit.name = "Sand Elemental"
	unit.asset = ["TcrsCustomModpack", "Units", "sand_elemental"]
	unit.max_hp = 40

	unit.spells.append(LeapAttack(damage=8, range=4))

	unit.flying = True
	unit.tags = [Tags.Elemental, Tags.Nature]
	unit.resists[Tags.Poison] = 100
	unit.resists[Tags.Physical] = 100

	return unit

class AdvancingSandBuff(Buff):
	def __init__(self, spell):
		Buff.__init__(self)
		self.name = "Call the Sandstorm"
		self.spell = spell
		self.buff_type = BUFF_TYPE_NONE
		self.stack_type = STACK_INTENSITY
		self.asset = ["TcrsCustomModpack", "Misc", "call_sandstorm"]
		self.description = "The sandstorm advances each turn."
		if self.spell.get_stat('blind_immune'):
			self.owner_triggers[EventOnBuffApply] = self.on_buffed
			self.resists[Tags.Physical] = 50
		self.y = 0
		
	def iter_tiles_swap(self):
		tiles = []
		i = 0
		j = 0
		while j < self.owner.level.height:
			tiles.append(self.owner.level.tiles[j][i])
			i += 1
			if i == self.owner.level.width:
				j += 1
				i = 0
		return tiles

	def on_advance(self):
		tiles = self.iter_tiles_swap()
		row = self.y
		height = self.owner.level.height
		if row + 2 >= height:
			row = height - 2
		for t in tiles:
			if t.y <= row + 2 and t.y >= row:
				c = self.spell.make_cloud(t.x, t.y)
				self.owner.level.add_obj(c, t.x, t.y)
		if row == height - 2:
			self.owner.remove_buff(self)
		self.y += 3

	def on_buffed(self, evt):
		if isinstance(evt.buff, BlindBuff):
			self.owner.remove_buffs(BlindBuff)

class AdvancingSandstorm(Spell):
	def on_init(self):
		self.name = "Advancing Sandstorm"
		self.tags = [Tags.Nature, Tags.Enchantment]
		self.level = 3
		self.asset = ["TcrsCustomModpack", "Icons", "advancing_sandstorm"]

		self.max_charges = 2
		self.damage = 2
		self.damage_type = [Tags.Physical]
		self.range = 0
		self.duration = 5

		self.can_target_self = True

		self.upgrades['sandworm'] = (1, 3, "Sandworm Spawning", "Fill all adjacent tiles with Clay Rockworms.", [Tags.Conjuration])
		self.upgrades['elemental'] = (1, 5, "Dust Elementals", "When a Sandstorm expires on a floor it has a 10% chance to turn into a sand elemental for 5 turns.", [Tags.Conjuration]) ## Chance effect
		self.upgrades['blind_immune'] = (1, 2, "Desert Mastery", "Gain 50% physical Resistance during the effect. You cannot be blinded by any source while the sandstorm advances, and the dust cloud blind lasts 3 turns.")

	def get_description(self):
		return ("Call the Sandstorm. Each turn the sandstorm moves, three rows at a time, from the top of the realm to the bottom, placing dust clouds on every tile.\n"
				"Dust clouds deal [{damage}_physical:physical] damage to units standing in them, and blind for 1 turn. Clouds last for [{duration}_turns:duration].\n"
				"Ends when the sandstorm reaches the bottom.").format(**self.fmt_dict())

	def make_cloud(self, x, y):
		if self.get_stat('cloak'):
			buff_duration = 3
		else:
			buff_duration = 1
		c = Sandstorm(owner=self.caster,damage=self.get_stat('damage'),duration = self.get_stat('duration'),buff_duration=buff_duration)
		c.location = Point(x, y)
		c.source = self
		if self.get_stat('elemental'):
			def on_expire(c):
				if not self.caster.level.tiles[c.location.x][c.location.y].is_floor():
					return
				if random.random() <= 0.90:
					return
				unit = SandElemental()
				unit.turns_to_death = self.get_stat('minion_duration',base=5)
				apply_minion_bonuses(self, unit)
				self.summon(unit, Point(c.location.x, c.location.y))
			c.on_expire = on_expire.__get__(c, Sandstorm)
		return c

	def cast(self, x, y):
		if self.get_stat('sandworm'):
			for p in self.owner.level.get_adjacent_points(self.caster, filter_walkable=True, check_unit=True):
				unit = RockWurm()
				BossSpawns.apply_modifier(Claytouched, unit)
				apply_minion_bonuses(self, unit)
				self.summon(unit, p)
		self.caster.apply_buff(AdvancingSandBuff(self))
		yield



def WizardBody(hp=1):
	unit = Unit()
	unit.name = "Wizard's Body"
	unit.asset = ["TcrsCustomModpack", "Units", "player_body"]
	unit.max_hp = hp
	unit.stationary = True
	unit.tags = [Tags.Living]
	return unit

class AstralLink(Buff):
	def __init__(self, spell, spirit):
		self.spell = spell
		self.spirit = spirit
		Buff.__init__(self)
		self.name = "Astral Link"
		self.asset = ["TcrsCustomModpack", "Misc", "astral_projection_buff"]
		self.buff_type = BUFF_TYPE_CURSE
		self.owner_triggers[EventOnDamaged] = self.on_dmg
		
	def on_advance(self):
		if not self.spell.get_stat('separate'):
			return
		if self.owner.level.can_see(self.spell.owner.x, self.spell.owner.y, self.owner.x, self.owner.y):
			return
		candidates = [u for u in self.owner.level.get_units_in_ball(self.owner, self.spell.get_stat('radius',base=6)) if are_hostile(u, self.spell.caster)]
		random.shuffle(candidates)
		for c in candidates[:3]:
			for p in self.owner.level.get_points_in_line(self.owner, c)[1:-1]:
				self.owner.level.show_effect(p.x, p.y, Tags.Dark, minor=True)
			c.deal_damage(self.spell.get_stat('damage',base=10), Tags.Dark, self.spell)

	def on_dmg(self, evt):
		self.spirit.deal_damage(evt.damage, Tags.Arcane, self)

class AstrallyProjected(Buff):
	def __init__(self, spell, body):
		self.spell = spell
		self.body = body
		Buff.__init__(self)
		self.name = "Astral Projection"
		self.buff_type = BUFF_TYPE_BLESS
		self.stack_type = STACK_TYPE_TRANSFORM
		self.asset = ["TcrsCustomModpack", "Misc", "astral_projection_buff"]
		self.transform_asset = ["TcrsCustomModpack", "Units", "player_projection"]
		self.resists[Tags.Physical] = 200
		self.resists[Tags.Fire] = 200
		self.resists[Tags.Ice] = 200
		self.resists[Tags.Lightning] = 200
		self.resists[Tags.Poison] = 200
		self.resists[Tags.Arcane] = -100
		self.owner_triggers[EventOnSpellCast] = self.on_cast
		
	def on_cast(self, evt):
		if not Tags.Translocation in evt.spell.tags:
			return
		if type(evt.spell) != type(AstralProjection_TCRS()):
			self.owner.remove_buff(self)
	
	def on_advance(self):
		if not self.spell.get_stat('separate'):
			return
		if self.owner.level.can_see(self.owner.x, self.owner.y, self.spell.unit.x, self.spell.unit.y):
			return
		candidates = [u for u in self.owner.level.get_units_in_ball(self.owner, self.spell.get_stat('radius',base=6)) if are_hostile(u, self.spell.caster)]
		random.shuffle(candidates)
		for c in candidates[:3]: ##TODO see if all of my empty checks could be replaced by this more elegant solution
			for p in self.owner.level.get_points_in_line(self.owner, c)[1:-1]:
				self.owner.level.show_effect(p.x, p.y, Tags.Arcane, minor=True)
			c.deal_damage(self.spell.get_stat('damage',base=10), Tags.Arcane, self.spell)

	def on_unapplied(self):
		if not self.body: ##Rare chance your body might die while you've healed up. Just become normal where you are. Maybe you should die?
			return
		point = Point(self.body.x, self.body.y)
		if not self.owner.level.can_walk(point.x, point.y): ##If corruption makes your tile a wall you're going to crash.
			return
		self.body.kill()
		self.spell.unit = None
		self.owner.level.act_move(self.spell.caster, point.x, point.y, teleport=True)

class AstralProjection_TCRS(Spell):
	def on_init(self):
		self.name = "Spirit Projection"
		self.tags = [Tags.Arcane, Tags.Translocation, Tags.Enchantment]
		self.level = 3
		self.asset = ["TcrsCustomModpack", "Icons", "astral_projection"]

		self.max_charges = 5
		self.range = 8
		self.duration = 4

		self.requires_los = -1
		self.quick_cast = True
		self.must_target_empty = True
		self.unit = None

		self.upgrades['daggers'] = (1, 2, "Spirit Dagger", "If there is an enemy adjacent to the target point, you cast your obsidian dagger on one adjacent unit.", [Tags.Fire])
		self.upgrades[('separate','damage')] = ([1,10], 2, "Separation", ("Each turn if you are not in line of sight of your body," + 
														" you deal [10_arcane:arcane] damage to up to 3 enemy units within a [6_tile:radius] radius and your body does the same effect but with [dark] damage."), [Tags.Dark])
		self.upgrades['cantrip'] = (1, 3, "Cantrip Mastery", "Your body knows your level 1 sorceries, each with a 2 turn cooldown.", [Tags.Sorcery])

	def get_description(self):
		return ("Move the wizard to target location, leaving your body behind for [{duration}_turns:duration] turns. Does not require line of sight.\n"
				"Become immune to all damage types except [Arcane], [Holy], and [Dark], lose 100 [Arcane] resistance. Any damage your body takes, is dealt to you as arcane."
				"You are still vulnerable to debuffs."
				"\nCasting any other translocation spell ends the effect.").format(**self.fmt_dict())

	def can_cast(self, x, y):
		return Spell.can_cast(self, x, y) and self.caster.level.can_move(self.caster, x, y, teleport=True)


	def cast(self, x, y):
		if self.unit == None:
			unit = WizardBody(self.caster.cur_hp)
			unit.tags = self.caster.tags
			unit.apply_buff(AstralLink(self, self.caster))
			if self.get_stat('cantrip'):
				spells = [s for s in self.caster.spells if s.level == 1 and Tags.Sorcery in s.tags]
				if spells != []:
					for cantrip in spells:
						grant_minion_spell(type(cantrip), unit, self.caster, 3)
			point = Point(self.caster.x, self.caster.y)
			self.unit = unit
			self.caster.level.show_effect(self.caster.x, self.caster.y, Tags.Translocation)
			self.caster.level.act_move(self.caster, x, y, teleport=True)
			self.summon(unit, point)
			self.caster.apply_buff(AstrallyProjected(self, unit), self.get_stat('duration'))
		else:
			self.caster.level.show_effect(self.caster.x, self.caster.y, Tags.Translocation)
			self.caster.level.act_move(self.caster, x, y, teleport=True)
			buff = self.caster.get_buff(AstrallyProjected)
			if buff:
				buff.turns_left = self.get_stat('duration')
		
		if self.get_stat('daggers'):
			units = []
			for p in self.caster.level.get_adjacent_points(Point(x, y)):
				unit = self.caster.level.get_unit_at(p.x, p.y)
				if unit and are_hostile(self.caster, unit):
					units.append(unit)
			if units != []:
				random.shuffle(units)
				spell = self.caster.get_or_make_spell(ObsidianDagger)
				self.caster.level.act_cast(self.owner, spell, units[0].x, units[0].y, pay_costs=False)

		yield



class Telekinesis(Spell):
	def on_init(self):
		self.name = "Telekinesis"
		self.tags = [Tags.Arcane, Tags.Translocation]
		self.level = 3
		self.asset = ["TcrsCustomModpack", "Icons", "telekinesis"]

		self.max_charges = 25
		self.range = 8

		self.damage = 60
		self.damage_type = [Tags.Arcane]
		self.unit = None
		self.point = None

		self.upgrades['volcano'] = (1, 2, "Into the Volcano", "If you target a chasm, cast your volcanic eruption on the chasm, and lose 4 charges of this spell.", [Tags.Fire])
		self.upgrades['wall'] = (1, 2, "Wall Slam", "If an enemy unit lands adjacent to a wall, or any enemy units, adjacent units take [10:physical] damage.")
		self.upgrades['passes'] = (1, 1, "Arcane Shift", "If an enemy unit is in the path of moved unit, deal [10:arcane] damage to them.",)

	def get_description(self):
		return ("Move target unit from its tile, to any other tile in range and stuns the unit for 2 turns.\nIf a non-flying unit is moved over a chasm it is removed without triggering death effects.\n"
				"Does not affect units with more than [{damage}_max_hp:arcane] max hp, scaling with damage, or units which gain clarity.").format(**self.fmt_dict())

	def get_impacted_tiles(self, x, y):
		point_unit = None
		if self.unit == None:
			self.unit = self.caster.level.get_unit_at(x, y)
		else:
			self.point = Point(x, y)
			point_unit = self.caster.level.get_unit_at(self.point.x, self.point.y)
		
		if point_unit and point_unit != self.unit:
			self.unit = None
			self.point = None
			return []
		
		if self.unit == None and self.point == None: 
			return []
		elif self.point != None and self.unit:
			return [Point(self.unit.x, self.unit.y), self.point]
		else:
			return []

	def cast(self, x, y):
		if self.unit != None and self.point != None:
			if self.unit.max_hp > self.get_stat('damage'):
				return
			if self.unit.gets_clarity:
				return
			start_point = Point(self.unit.x, self.unit.y)
			tile = self.caster.level.tiles[self.point.x][self.point.y]
			kill_flag = False
			self.unit.apply_buff(Stun(),2)
			if tile.is_chasm and self.unit.flying == False:
				kill_flag = True
				self.unit.flying = True
			self.caster.level.act_move(self.unit, self.point.x, self.point.y, teleport=True)
			if kill_flag:
				self.unit.kill(trigger_death_event=False)
				
			for p in self.caster.level.get_points_in_line(start_point, self.point)[1:-1]:
				if self.get_stat('passes'):
					unit = self.caster.level.get_unit_at(p.x, p.y)
					if unit != None and are_hostile(self.caster, unit):
						self.caster.level.deal_damage(p.x, p.y, self.get_stat('damage',base=10), Tags.Arcane, self)
				self.caster.level.show_effect(p.x, p.y, Tags.Translocation)
				
			if self.get_stat('wall'):
				slam = False
				for p in self.caster.level.get_adjacent_points(Point(x, y), filter_walkable=False):
					if self.caster.level.tiles[p.x][p.y].is_wall():
						slam = True
					unit = self.caster.level.get_unit_at(p.x, p.y)
					if unit != None and unit != self.unit:
						slam = True
						self.caster.level.deal_damage(p.x, p.y, self.get_stat('damage',base=10), Tags.Physical, self)
				if slam == True:
					self.caster.level.deal_damage(self.point.x, self.point.y, self.get_stat('damage',base=10), Tags.Physical, self)

			if self.get_stat('volcano') and tile.is_chasm:
				eruption = self.caster.get_or_make_spell(Volcano)
				self.caster.level.act_cast(self.caster, eruption, tile.x, tile.y, pay_costs=False)
				if self.cur_charges >= 4:
					self.cur_charges -= 4
				else:
					self.cur_charges = 0

		self.unit = None
		self.point = None
		yield



class TridentOfWoe(Spell):
	def on_init(self):
		self.name = "Woeful Strike"
		self.tags = [Tags.Ice, Tags.Lightning, Tags.Dark, Tags.Sorcery]
		self.asset = ["TcrsCustomModpack", "Icons", "woe_trident"]
		self.level = 3
		self.range = 7
		self.radius = 2
		self.max_charges = 12
		self.damage = 15
		self.damage_type = [Tags.Ice, Tags.Lightning, Tags.Dark]
		self.damage_dealt = [0, 0, 0]
		
		self.upgrades['mastery'] = (1, 4, "Mastery", "If you have spent 20 or more points in [Ice] magic, deal 1 [Ice] damage to all enemies in line of sight. Then repeat for [Lightning] and [Dark] magic. This damage is fixed.")
		self.upgrades['spirits'] = (1, 6, "Spirit Allies", "For each 150 damage dealt by the [Ice] beam, summon a ghostly storm spirit for [36:minion_duration] turns. Repeat for [Lightning] and [Dark]", [Tags.Conjuration])
		self.upgrades['box'] = (1, 6, "Box of Woe", "If at least 10 damage was dealt by each of the different beams, summon a box of woe for [6:minion_duration] turns at the target tile.", [Tags.Conjuration])

	def get_description(self):
		return ("Deal [{damage}_ice:ice] damage in a beam towards target point, then deal the same amount of damage as [Lightning] and [Dark] in 2 beams forking from the first tile of the beam."
				"Cannot be used in melee range.").format(**self.fmt_dict())

	def can_cast(self, x, y):
		if distance(Point(x, y), self.caster, diag=True) <= 1 + self.owner.radius:
			False
		else:
			return Spell.can_cast(self, x, y)

	def get_targetable_tiles(self):
		candidates = self.caster.level.get_points_in_ball(self.caster.x, self.caster.y, self.get_stat('range'))
		return [p for p in candidates if self.can_cast(p.x, p.y) and distance(Point(self.caster.x, self.caster.y), Point(p.x, p.y)) >= 1.5]

	def get_tiles_trident(self, x, y):
		lines = []
		mid_line = self.caster.level.get_points_in_line(self.caster, Point(x, y), two_pass=True, find_clear=True)
		mid_line = mid_line[1:]
		lines.append(mid_line)
		ends = self.caster.level.get_perpendicular_line(self.caster, Point(x, y), length=self.get_stat('radius'))
		lines.append(self.caster.level.get_points_in_line(mid_line[0], ends[0], two_pass=True))
		lines.append(self.caster.level.get_points_in_line(mid_line[0], ends[-1], two_pass=True))
		return lines

	def get_impacted_tiles(self, x, y):
		tiles = self.get_tiles_trident(x, y)
		all_tiles = []
		for tile_list in tiles:
			for t in tile_list:
				all_tiles.append(t)
		return all_tiles

	def cast(self,x,y):
		tile_list = self.get_tiles_trident(x, y)
		middle = tile_list[0]
		side_lightning = tile_list[1]
		side_dark = tile_list[2]
		damage_dealt = [0, 0, 0]
		for t in middle:
			damage_dealt[0] += self.caster.level.deal_damage(t.x, t.y, self.get_stat('damage'), Tags.Ice, self)
		for t in side_lightning:
			damage_dealt[1] += self.caster.level.deal_damage(t.x, t.y, self.get_stat('damage'), Tags.Lightning, self)
		for t in side_dark:
			damage_dealt[2] += self.caster.level.deal_damage(t.x, t.y, self.get_stat('damage'), Tags.Dark, self)
		
		targets = [u for u in self.caster.level.get_units_in_los(Point(x,y)) if u != self.caster and are_hostile(self.caster, u)]
		if self.get_stat('mastery') and self.owner.get_mastery(Tags.Ice) >= 20:
			for t in targets:
				self.caster.level.deal_damage(t.x, t.y, 1, Tags.Ice, self)
		if self.get_stat('mastery') and self.owner.get_mastery(Tags.Lightning) >= 20:
			for t in targets:
				self.caster.level.deal_damage(t.x, t.y, 1, Tags.Lightning, self)
		if self.get_stat('mastery') and self.owner.get_mastery(Tags.Dark) >= 20:
			for t in targets:
				self.caster.level.deal_damage(t.x, t.y, 1, Tags.Dark, self)

		if self.get_stat('box') and damage_dealt[0] >= 10 and damage_dealt[1] >= 10 and damage_dealt[2] >= 10: 
			unit = BoxOfWoe()
			unit.turns_to_death = 6
			apply_minion_bonuses(self, unit)
			self.summon(unit,Point(x,y))
		for i in range(2):
			self.damage_dealt[i] += damage_dealt[i]
			if self.get_stat('spirits') and self.damage_dealt[i] >= 150:
				self.damage_dealt[i] -= 150
				unit = StormSpirit()
				unit.turns_to_death = 36
				apply_modifier(Ghostly,unit)
				apply_minion_bonuses(self, unit)
				self.summon(unit,Point(self.caster.x,self.caster.y))

		yield



class ReformingSwarm(Buff):
	def __init__(self,spell=None):
		Buff.__init__(self)
		self.name = "Reforming Swarm"
		self.buff_type = BUFF_TYPE_BLESS
		self.color = Tags.Nature.color
		self.description = "Reform the mage with the combined HP of all units sharing the buff, when the buff expires."
		self.stack_type = STACK_DURATION
		self.spell = spell
		
	def on_advance(self):
		if self.turns_left == 1:
			cur_hp = 0
			units = [u for u in self.owner.level.units if not are_hostile(u, self.owner) and u.has_buff(ReformingSwarm)]
			for u in units:
				cur_hp += u.cur_hp
				self.owner.level.show_effect(u.x, u.y, Tags.Dark)
				u.kill()
			if self.spell == None:
				unit = GristMage(cur_hp)
				owner = unit
			else:
				unit = self.spell.make_mage(cur_hp)
				owner = self.spell.caster
			self.owner.level.summon(owner=owner, unit=unit, target=self.owner)
			buff = unit.get_buff(ReformingSpawn)
			buff.spell = self.spell
			unit.source = self.spell

class ReformingSpawn(SpawnOnDeath):
	def __init__(self, spawner, num_spawns):
		SpawnOnDeath.__init__(self, spawner, num_spawns)
		self.spell = None
		self.description = "On death, spawn 1 fly swarm for each 6 max hp.\nReform if any remain after 5 turns with the total hp of the flies."

	def spawn(self):
		self.owner.max_hp = int(self.owner.max_hp)
		self.num_spawns = self.owner.max_hp // 6
		for i in range(self.num_spawns):
			unit = self.spawner()
			if self.owner.source and self.apply_bonuses:
				unit.source = self.owner.source
			if self.spell != None:
				if self.spell.get_stat('growing'):
					apply_minion_bonuses(self.spell, unit)
					unit.max_hp = 9
			self.summon(unit)
			unit.apply_buff(ReformingSwarm(self.spell), 5)
			unit.source = self.spell
			yield

def GristMage(hp=114):
	unit = Unit()
	unit.name = "Gristmage"
	unit.asset = ["TcrsCustomModpack", "Units", "gristmage"]
	unit.tags = [Tags.Nature, Tags.Dark]
	unit.max_hp = hp
	unit.resists[Tags.Physical] = 75
	unit.resists[Tags.Dark] = 75
	unit.resists[Tags.Holy] = -75
	unit.resists[Tags.Ice] = -75
	unit.resists[Tags.Fire] = -100
	unit.flying = True
	#proj_name = [["TcrsCustomModpack", "Misc", "swarm_shot"]] ##TODO figure out ##figured out, incorporate sometime
	unit.spells.append(SimpleRangedAttack(name="Swarmshot", damage=unit.max_hp//10, damage_type=Tags.Physical, range=5,proj_name="petrification"))
	melee_attack = SimpleMeleeAttack(damage=2, damage_type=Tags.Dark, drain=True,attacks=3)
	melee_attack.name="Biting Flies"
	unit.spells.append(melee_attack)
	unit.buffs.append(RegenBuff(6))
	unit.buffs.append(ReformingSpawn(FlyCloud,19)) ##Sets number in buff
	return unit

class Flylord(Upgrade):
	def on_init(self):
		self.level = 5
		self.name = "Swarm-that-walks"
		self.description = "You passively spawn a fly cloud every 4 turns. Your Gristmages summon flies on hit with their Swarmshot and Biting Flies spells."
		self.count = 4
		self.tags = [Tags.Dark, Tags.Nature, Tags.Conjuration]
		self.minion_health = 6
		self.minion_damage = 2

	def on_advance(self):
		self.count -= 1
		if self.count > 0:
			return
		self.count = 4
		unit = FlyCloud()
		unit.max_hp = 3 + (self.get_stat('minion_health') // 2)
		for s in unit.spells:
			if hasattr(s, 'damage'):
				s.damage = 1 + (self.get_stat('minion_damage') // 2)
		self.summon(unit, self.owner)

class Grist(Spell):
	def on_init(self):
		self.name = "Gristmage" ##Other potential names: Swarm-that-walks, The Swarm
		self.tags = [Tags.Nature, Tags.Dark, Tags.Conjuration]
		self.asset = ["TcrsCustomModpack", "Icons", "gristmage_icon"]
		self.level = 5
		
		self.max_charges = 15
		self.minion_health = 6
		self.minion_damage = 2
		self.minion_range = 5
		self.range = 3
		self.must_target_empty = True

		## Upgrade that causes gristmages to absorb nearby flyclouds to gain 6 max hp.
		self.upgrades['growing'] = (1, 5, "Hungering Tide", "The max hp per charge increases to 9, and flies summoned by the gristmage have 9 hp and benefit from bonuses to minion damage.")
		self.upgrades['plague'] = (1, 4, "Plague Caller", "The Gristmage can cast your plague of filth spell with a 30 turn cooldown.")
		self.add_upgrade(Flylord())

	def get_description(self):
		return ("Summon a gristmage at target tile.\nThe gristmage has a physical ranged attack that deals 10% of its max life and a dark life draining melee attack.\n"
				"On death it spawns fly clouds for each 6 max hp it had, which last 5 turns, and if any remain it respawns with their combined hp.\n"
				"Consumes all charges on cast, granting the gristmage 6 max hp for each one.").format(**self.fmt_dict())

	def make_mage(self, hp):
		unit = GristMage(hp)
		if self.get_stat('plague'):
			spell = grant_minion_spell(Spells.PlagueOfFilth, unit, self.caster, 30)
			spell.description = ("Summon a group of toads and fly swarms.")
		return unit

	def get_extra_examine_tooltips(self): 
		return [self.make_mage(6), self.spell_upgrades[0], self.spell_upgrades[1], self.spell_upgrades[2], FlyCloud()]

	def cast(self, x, y):
		charge_hp = self.cur_charges * 6
		if self.get_stat('growing'):
			charge_hp *= 1.5
		self.cur_charges = 0
		unit = self.make_mage(6 + charge_hp)
		if self.caster.has_buff(Flylord):
			def summon_fly(grist, target):
				flycloud = FlyCloud()
				grist.level.summon(grist, flycloud, target)
			unit.spells[0].onhit=summon_fly
			unit.spells[1].onhit=summon_fly
		apply_minion_bonuses(self, unit)
		self.summon(unit, Point(x,y))
		buff = unit.get_buff(ReformingSpawn)
		buff.spell = self
		yield



class Clairvoyance(Upgrade):
	def on_init(self):
		self.level = 1
		self.name = "Clairvoyance"
		self.description = ("You can see the tile that you are going to be teleported to that turn. If it becomes occupied you don't teleport.")
		self.point = Point(0,0)

	def get_walkable_tile(self):
		possible_points = []
		for i in range(len(self.owner.level.tiles)):
			for j in range(len(self.owner.level.tiles[i])):
				if self.owner.level.can_stand(i, j, self.owner):
					possible_points.append(Point(i, j))
		if not possible_points:
			return
		tile = random.choice(possible_points)
		if tile == None:
			return
		self.point = tile

	def on_applied(self, owner):
		self.get_walkable_tile()

	def on_pre_advance(self):
		self.get_walkable_tile()

class RandomTeleport(Spell):
	def on_init(self):
		self.name = "Random Escape"
		self.tags = [Tags.Chaos, Tags.Sorcery, Tags.Translocation]
		self.level = 2
		self.asset = ["TcrsCustomModpack", "Icons", "chaotic_escape"]

		self.max_charges = 10
		self.range = 0
		self.self_target = True

		self.upgrades['orby'] = (1, 4, "Back-orb", "Cast a random orb spell you know on the tile you teleported from, if there is space. Consume 2 charges from this spell.", [Tags.Orb])
		self.upgrades['slimy'] = (1, 6, "Slimy Rainbow", "Summon random slimes on empty floor tiles between the points you teleported to and from. They last for a random number of turns between 5 and 30.", [Tags.Slime])
		self.add_upgrade(Clairvoyance())

	def get_description(self):
		return ("Teleport to a random tile that you can stand on.").format(**self.fmt_dict())
	
	def get_impacted_tiles(self, x, y):
		buff = self.caster.get_buff(Clairvoyance)
		if buff == None:
			return [Point(x, y)]
		else:
			return [buff.point]

	def cast(self,x,y):
		buff = self.caster.get_buff(Clairvoyance)
		if buff == None:
			tile = self.get_walkable_point()
		else:
			tile = buff.point
		if tile == None or self.caster.level.get_unit_at(tile.x,tile.y) != None:
			return
		self.caster.level.show_effect(x, y, Tags.Translocation)
		self.caster.level.act_move(self.caster, tile.x, tile.y, teleport=True)
		for p in self.caster.level.get_points_in_line(Point(x, y), tile)[1:-1]:
			eff_tag = random.choice([Tags.Arcane, Tags.Chaos, Tags.Translocation])
			self.caster.level.show_effect(p.x, p.y, eff_tag, minor=True)
			if self.caster.level.tiles[p.x][p.y].is_floor() and self.get_stat('slimy'):
				slime = random.choice([GreenSlime(), RedSlime(), VoidSlime(), IceSlime()])
				slime.turns_to_death = random.randint(5,30)
				apply_minion_bonuses(self, slime)
				self.summon(slime, Point(p.x, p.y))
		if self.get_stat('orby'):
			orb_spells = [s for s in self.caster.spells if Tags.Orb in s.tags]
			if not orb_spells == []:
				spell = random.choice(orb_spells)
				self.caster.level.act_cast(self.caster, spell, x, y, pay_costs=False)
				self.cur_charges -= 2
			
		yield

	def get_walkable_point(self):
		possible_points = [] ##Word of chaos, but for you
		for i in range(len(self.caster.level.tiles)):
			for j in range(len(self.caster.level.tiles[i])):
				if self.caster.level.can_stand(i, j, self.caster):
					possible_points.append(Point(i, j))
		if not possible_points:
			return
		tile = random.choice(possible_points)
		return tile



class TrueNameEffect(Buff):
	def __init__(self, spell, target):
		Buff.__init__(self)
		self.spell = spell
		self.target = target
		self.name = target + " Curse"
		self.description = "Deal damage to any unit which enters or casts a spell, whose name is: " + target

	def on_init(self):
		self.buff_type = BUFF_TYPE_BLESS
		self.stack_type = STACK_REPLACE
		self.color = Tags.Arcane.color
		self.global_triggers[EventOnSpellCast] = self.on_cast
		self.global_triggers[EventOnUnitAdded] = self.on_add
		self.removing = False

	def on_cast(self, evt):
		if evt.caster.name == self.target:
			self.owner.level.deal_damage(evt.caster.x, evt.caster.y, self.spell.get_stat('damage'), Tags.Arcane, self.spell)
			if not self.spell.get_stat('length'):
				return
			for letter in evt.caster.name:
				self.owner.level.deal_damage(evt.caster.x, evt.caster.y, 5, Tags.Dark, self.spell)
				
	def on_add(self, evt):
		if evt.unit.is_player_controlled:
			self.removing = True
			self.owner.remove_buff(self)
		if evt.unit.name == self.target:
			self.owner.level.deal_damage(evt.unit.x, evt.unit.y, self.spell.get_stat('damage'), Tags.Arcane, self.spell)
			if not self.spell.get_stat('length'):
				return
			for letter in evt.unit.name:
				self.owner.level.deal_damage(evt.unit.x, evt.unit.y, 5, Tags.Dark, self.spell)

	def on_unapplied(self):
		if self.spell.get_stat('prevent') and not self.removing:
			self.owner.apply_buff(TrueNameEffect(self.spell, self.target), self.spell.get_stat('duration'))

class TrueNameCurse(Spell):
	def on_init(self):
		self.name = "True Name Curse"
		self.tags = [Tags.Arcane, Tags.Enchantment]
		self.level = 8
		self.asset = ["TcrsCustomModpack", "Icons", "truenamecurse"]

		self.max_charges = 5
		self.damage = 25
		self.damage_type = [Tags.Arcane]
		self.range = 12
		self.duration = 30
		self.can_target_empty = False

		
		self.upgrades['single'] = (1, 5, "Hapax legomenon", "If you target a unit which does not share an exact name with any other unit in the realm, deal [666:holy] damage to it.", [Tags.Holy])
		self.upgrades['length'] = (1, 6, "Sesquipedalian", "Also deals [3:damage] [dark] damage to a unit for each letter in that unit's name. This damage is fixed.", [Tags.Dark])
		self.upgrades['prevent'] = (1, 4, "Impreventable", "The buff reapplies itself when it is removed, and lasts until you enter a new realm.")

	def get_description(self):
		return ("Target a unit to gain the true name curse for [{duration}_turns:duration].\nWhen any unit with the same name enters the realm or casts a spell, "
				" deal [{damage}_damage:arcane] damage to the unit.").format(**self.fmt_dict())

	def cast(self, x, y):
		unit = self.caster.level.get_unit_at(x, y)
		name = unit.name
		self.caster.apply_buff(TrueNameEffect(self, name), self.get_stat('duration'))
		all_units = [u for u in self.caster.level.units if u.name == name]
		print(all_units)
		if all_units == []:
			pass
		elif len(all_units) == 1 and self.get_stat('single'):
			unit.deal_damage(666, Tags.Holy, self)
		yield



class GalvanizationTransformation(Buff):
	def __init__(self, spell=None):
		self.spell = spell
		Buff.__init__(self)
		
	def on_init(self):
		self.buff_type = BUFF_TYPE_BLESS
		self.stack_type	= STACK_TYPE_TRANSFORM
		self.transform_asset = ["TcrsCustomModpack", "Units", "galvanni_beast_active"]
		self.description = "Remains awake for only a limited amount of time."
		self.devour = None

	def on_applied(self, owner):
		self.owner.stationary = False
		if self.spell == None:
			damage = 30
		else:
			damage = self.spell.get_stat('minion_damage')
		devour = SimpleMeleeAttack(damage=damage,damage_type=Tags.Physical, buff=FearBuff, buff_duration=2)
		devour.caster = self.owner
		devour.owner = self.owner
		if self.spell.get_stat('lifesteal'):
			devour.drain = True
			def hit_extend(a, b):
				self.turns_left += self.spell.get_stat('minion_duration',base=3)
			devour.onhit = hit_extend
		self.devour = devour
		self.owner.spells.append(devour)

	def on_unapplied(self):
		self.owner.stationary = True
		for s in self.owner.spells:
			if s == self.devour:
				self.owner.spells.remove(s)

class GalvanizationTriggers(Buff):
	def __init__(self, spell=None):
		self.spell = spell
		Buff.__init__(self)
	def on_init(self):
		self.buff_type = BUFF_TYPE_PASSIVE
		self.stack_type	= STACK_NONE
		self.count = 20
		self.blood_remainder = 0
		if self.spell != None:
			self.description = "Awakens when it takes [lightning] damage, then heals for that much damage."
			self.owner_triggers[EventOnDamaged] = self.on_dmg
			self.global_triggers[EventOnSpendHP] = self.spend_hp

	def on_advance(self):
		if self.spell == None:
			self.count -= 1
			self.description = "Awakens after " + str(self.count) + " turns."
			if self.count <= 0:
				buff = GalvanizationTransformation()
				self.owner.apply_buff(buff)
				self.owner.remove_buff(self)
		else:
			if self.spell.get_stat('cloud'):
				tile = self.owner.level.tiles[self.owner.x][self.owner.y]
				if isinstance(tile.cloud, (BlizzardCloud, StormCloud)):
					cloud = RainCloud(self.spell.caster,self.spell)
					cloud.duration = tile.cloud.duration
					tile.cloud.kill()
					self.owner.level.add_obj(cloud, tile.x, tile.y)
					self.transformation(self.spell.get_stat('duration',base=4))
					self.owner.advance()

	def end_advance(self):
		pass

	def transformation(self, duration):
		buff = self.owner.get_buff(GalvanizationTransformation)
		if buff == None:
			buff = GalvanizationTransformation(self.spell)
			self.owner.apply_buff(buff, duration)
		else:
			buff.turns_left += duration

	def spend_hp(self, evt):
		self.transformation(self.spell.get_stat('duration'))

	def on_dmg(self, evt):
		if evt.damage_type == Tags.Lightning:
			self.owner.level.deal_damage(self.owner.x, self.owner.y, -evt.damage, Tags.Heal, self)
			self.transformation(self.spell.get_stat('duration'))
		elif self.spell == None:
			return
		else:
			if evt.damage_type == Tags.Fire and self.spell.get_stat('furnace'):
				self.transformation(self.spell.get_stat('duration'))

def GalvanizedHorror(spell=None):
	unit = Unit()
	unit.tags = [Tags.Blood, Tags.Lightning]
	unit.max_hp = 320
	unit.name = "Galvanized Horror"
	unit.asset = ["TcrsCustomModpack", "Units", "galvanni_beast_dorm"]
	unit.resists[Tags.Dark] = 50
	unit.resists[Tags.Physical] = 50
	unit.resists[Tags.Holy] = -50
	unit.resists[Tags.Ice] = -50
	unit.resists[Tags.Arcane] - 50
	unit.stationary = True
	unit.buffs.append(Thorns(12,Tags.Lightning))
	if spell == None:
		unit.buffs.append(GalvanizationTriggers())
	else:
		unit.buffs.append(GalvanizationTriggers(spell))
	return unit

class GalvanizedSummon(Spell):
	def on_init(self):
		self.name = "Galvanized Horror"
		self.tags = [Tags.Blood, Tags.Lightning, Tags.Conjuration]
		self.level = 7
		self.asset = ["TcrsCustomModpack", "Icons", "galvanni_beast_icon"]
		self.hp_cost = 40

		self.max_charges = 2
		self.minion_health = 320
		self.minion_damage = 30
		self.duration = 2

		self.upgrades['lifesteal'] = (1, 5, "Lifestealer", "Extends awakening for [3:duration] turns after using its melee attack, and its melee attack drains life.")
		self.upgrades['furnace'] = (1, 2, "Furnace Beast", "Awakens or extends awakening from [fire] damage like it does [lightning] damage, but this does not cause healing.", [Tags.Fire])
		self.upgrades['cloud'] = (1, 2, "Cloudbuster", "Awakens or extends awakening for [4:duration] turns by converting a lightning storm or blizzard cloud on its tile into a rain cloud. Also grants the horror an extra turn.", [Tags.Ice])

		self.must_target_walkable = True
		self.must_target_empty = True

	def get_description(self):
		return ("Summon a dormant horror with [{minion_health}_HP:minion_health].\nThe horror deals 12 [lightning] damage to melee attackers, and when awakened deals [{minion_damage}_physical:physical] damage in melee.\n"
				"When any hp is spent on blood spells, or it takes lightning damage, it awakens for [{duration}_turns:duration] turn. It heals for 100% of all lightning damage taken.\n").format(**self.fmt_dict())

	def get_extra_examine_tooltips(self):
		return [GalvanizedHorror(), self.spell_upgrades[0]]

	def cast(self, x, y):
		unit = GalvanizedHorror(self)
		apply_minion_bonuses(self, unit)
		unit.turns_to_death = None
		self.summon(unit=unit, target=Point(x,y))
		yield



class JekylBuff(Stun):
	def __init__(self, spell):
		Stun.__init__(self)
		self.spell = spell
		for tag in damage_tags:
			if tag != Tags.Arcane or tag != Tags.Holy:
				self.resists[tag] = 50
		if self.spell.get_stat('regen'):
			self.resists[Tags.Poison] = 50
			self.resists[Tags.Arcane] = 50
			self.resists[Tags.Holy] = 50
		if self.spell.get_stat('rage'):
			self.owner_triggers[EventOnSpellCast] = self.on_cast
			self.owner_triggers[EventOnDamaged] = self.on_dmg

	def on_applied(self, owner):
		self.name = "ENRAGED!"
		self.color = Tags.Chaos.color

	def on_advance(self):
		self.owner.deal_damage(-self.spell.get_stat('damage'), Tags.Heal, self.spell)
		if self.spell.get_stat('rage'):
			self.owner.apply_buff(BloodrageBuff(1),self.spell.get_stat('duration'))
			
		possible_targets =  self.owner.level.get_units_in_ball(self.owner, self.spell.get_stat('radius'))
		possible_targets = [t for t in possible_targets if self.owner.level.are_hostile(t, self.owner)]
		possible_targets = [t for t in possible_targets if self.owner.level.can_see(t.x, t.y, self.owner.x, self.owner.y)]
		if possible_targets:
			random.shuffle(possible_targets)
			target = possible_targets[0]
			target = min(possible_targets, key=lambda t: distance(t, self.owner))
			self.owner.level.queue_spell(self.slash(target, distance(target, self.owner)))
		else:
			tiles = []
			for p in self.owner.level.get_adjacent_points(Point(self.owner.x, self.owner.y), filter_walkable=True):
				tiles.append(p)
			if tiles != []:
				tile = random.choice(tiles)
				if self.owner.level.can_move(self.owner, tile.x, tile.y, teleport=False):
					self.owner.level.act_move(self.owner, tile.x, tile.y, teleport=False)

	def slash(self, target, dist):
		if dist >= 1.5:
			spell = LeapAttack(damage=self.spell.get_stat('damage'), range=99, damage_type=Tags.Physical, is_leap=True)
			#if self.spell.get_stat('drain'): ##Maybe implement through some arcane upgrade
			#	spell.requires_los = False
		else:
			attacks = self.spell.get_stat('num_targets')
			spell = SimpleMeleeAttack(damage=self.spell.get_stat('damage'), damage_type=Tags.Physical, attacks=attacks)
			if self.spell.get_stat('drain'):
				spell.drain = True
				spell.damage_type = Tags.Dark
		spell.caster = self.owner
		spell.owner = self.owner
		spell.name = "Raging Claws"
		spell.tags = self.spell.tags
		spell.level = 1
		self.owner.level.act_cast(self.owner, spell, target.x, target.y, pay_costs=False, queue=True)
		yield

	def on_cast(self, evt):
		self.owner.apply_buff(BloodrageBuff(1),self.spell.get_stat('duration'))

	def on_dmg(self, evt):
		self.owner.apply_buff(BloodrageBuff(1),self.spell.get_stat('duration'))

class JekylAsset(Buff):
	def on_init(self):
		self.name = "Transformed"
		self.stack_type = STACK_TYPE_TRANSFORM
		self.buff_type = BUFF_TYPE_CURSE
		self.transform_asset = ["TcrsCustomModpack", "Units", "player_jekyl"]

class JekylPotion(Spell):
	def on_init(self):
		self.name = "Rage Potion"
		self.level = 4
		self.asset = ["TcrsCustomModpack", "Icons", "jekyl_potion"]
		self.tags = [Tags.Enchantment, Tags.Chaos, Tags.Nature, Tags.Translocation]

		self.max_charges = 8
		self.range = 0
		self.duration = 4
		self.damage = 5
		self.damage_type = [Tags.Physical]
		self.radius = 6
		self.num_targets = 4

		self.upgrades['rage'] = (1, 3, "Ulfsaar Drink", "Each turn, each spell you cast, and each time you take damage during the buff, grants you a stack of bloodrage. Each stack lasts [4:duration] turns.", [Tags.Blood])
		self.upgrades['regen'] = (1, 4, "Razzil Brew", "The regeneration effect is 5 times as strong, and gain an additional 50 [poison], [holy], and [arcane] resistance during the effect.")
		self.upgrades['drain'] = (1, 2, "N'aix Tonic", "The melee attacks become [dark], and drain life.", [Tags.Dark])

	def get_extra_examine_tooltips(self):
		return [self.spell_upgrades[0], self.spell_upgrades[1], self.spell_upgrades[2]]

	def get_description(self):
		return ("Each turn, attack an adjacent enemy [{num_targets}:num_targets] times, or if there are no adjacent units leap to an enemy within [{radius}_tiles:radius] tiles.\n"
				"Deals [{damage}_physical:physical] per hit. Lasts [{duration}_turns:duration]\n"
				"You are stunned during the effect, regenerate [{damage}_HP:heal] per turn, and gain 50% resistance to all damage types except [holy] and [arcane].\n"
				"The melee attack and leaps are level 1 spells with this spell's tags.").format(**self.fmt_dict())

	def cast_instant(self, x, y):
		self.caster.apply_buff(JekylBuff(self), self.get_stat('duration'))
		self.caster.apply_buff(JekylAsset(), self.get_stat('duration'))



class ChromaThief(Buff):
	def on_init(self):
		self.buff_type = BUFF_TYPE_PASSIVE
		self.global_triggers[EventOnDeath] = self.on_death
		
	def on_death(self, evt):
		if evt.damage_event:
			if evt.damage_event.source:
				if evt.damage_event.source.owner == self.owner:
					self.steal_tag(evt.unit)
				
	def steal_tag(self, unit):
		for tag in unit.tags:
			if tag not in self.owner.tags:
				self.owner.tags.append(tag)
				self.owner.max_hp += unit.max_hp
				self.owner.cur_hp += unit.max_hp
				break

def Riftstalker():
	unit = Unit()
	unit.name = "Riftstalker"
	unit.asset = ["TcrsCustomModpack", "Units", "riftstalker"]
	unit.max_hp = 25
	unit.shields = 4

	leap = LeapAttack(damage=9, range=3, is_leap=True, damage_type=Tags.Arcane)
	leap.requires_los = False
	unit.spells.append(leap)
	unit.buffs.append(TeleportyBuff())
	unit.tags = [Tags.Arcane, Tags.Chaos, Tags.Translocation]
	unit.resists[Tags.Arcane] = 100
	unit.resists[Tags.Holy] = -50
	unit.resists[Tags.Physical] = -50

	return unit

class SummonRiftstalker(Spell):
	def on_init(self):
		self.name = "Summon Riftstalker"
		self.tags = [Tags.Arcane, Tags.Conjuration, Tags.Chaos]
		self.level = 5
		self.asset = ["TcrsCustomModpack", "Icons", "riftstalker_icon"]

		self.max_charges = 2
		self.range = 3
		self.shields = 4
		self.minion_health = 25
		self.minion_damage = 9
		self.minion_range = 3

		self.must_target_empty = True

		self.upgrades['warp'] = (1, 3, "Warpstalker", "The leaping attack gains bonus range equal to the greatest range among your other [translocation] spells, and bonus damage equal to the SP you have spent on [translocation] magic.", [Tags.Translocation])
		self.upgrades['mind'] = (1, 2, "Mindmelter", "The spell silences you on cast for 3 turns, but hastes the riftstalker for 3 turns for every [Fire] or [Lightning] spell you know.", [Tags.Fire, Tags.Lightning])
		self.upgrades['conj'] = (1, 9, "Spellsucker", "Every other [conjuration] spell you know adds 25% of its minion health to the riftstalker. Repeat with minion damage and minion range, given to its leap attack.")

	def get_extra_examine_tooltips(self):
		return [Riftstalker(), self.spell_upgrades[0], self.spell_upgrades[1], self.spell_upgrades[2]]

	def get_description(self):
		return ("Summons a riftstalker at target tile.\nIts base hp is [{minion_health}_HP:minion_health] its base shields are [{shields}:shields], and "
				"it has a leaping attack which deals [{minion_damage}_arcane:arcane] with a range of [{minion_range}_tiles:minion_range].\n"
				"If you target a rift with the spell, the riftstalker's base minion health, damage, and shields are doubled.").format(**self.fmt_dict())

	## Known problems with spider queen. Can be solved with a few if conditions if I want to, but it's kind of an ugly if condition
	def cast_instant(self, x, y):
		unit = Riftstalker()
		unit.shields = self.get_stat('shields')
		if self.get_stat('warp'):
			bonus_range = 0
			for s in self.caster.spells:
				if Tags.Translocation not in s.tags or s.name == "Summon Riftstalker":
					continue
				if s.get_stat('range') > bonus_range:
					bonus_range = s.get_stat('range')
			unit.spells[0].range += bonus_range
			unit.spells[0].damage += self.caster.get_mastery(Tags.Translocation)
		
		if self.get_stat('conj'):
			attr_dict = {'minion_health':0, 'minion_damage':0, 'minion_range':0}
			for s in self.caster.spells:
				if Tags.Conjuration not in s.tags or s.name == "Summon Riftstalker":
					continue
				for a in attr_dict.keys():
					if not hasattr(s,a):
						continue
					attr = s.get_stat(a)
					attr_dict[a] += attr//4
			unit.max_hp += attr_dict['minion_health']
			unit.spells[0].damage += attr_dict['minion_damage']
			unit.spells[0].range += attr_dict['minion_range']

		t = self.caster.level.tiles[x][y]
		if t == None:
			pass
		elif type(t.prop) == Portal:
			unit.shields += 4
			unit.max_hp *= 2
			unit.spells[0].damage *= 2
			
		apply_minion_bonuses(self, unit)
		self.summon(unit, target=Point(x, y))
		
		if self.get_stat('mind'):
			count = 0
			for s in self.caster.spells:
				if Tags.Lightning in s.tags or Tags.Fire in s.tags:
					count += 1
			self.caster.apply_buff(Silence(), 10)
			unit.apply_buff(HasteBuff(), self.get_stat('duration',base=count*3))

class Reflector(Buff):
	def __init__(self, spell):
		Buff.__init__(self)
		self.name = "Reflection"
		self.spell = spell
		self.buff_type = BUFF_TYPE_NONE
		self.description = "The first [enchantment] spell, each turn, that you cast targeting the idol, is recast by the idol at a random enemy in line of sight."
		self.global_triggers[EventOnSpellCast] = self.on_cast
		self.copying = False


	def on_cast(self, evt):
		if self.copying == True:
			return
		if not evt.caster.is_player_controlled:
			return
		if evt.x != self.owner.x or evt.y != self.owner.y:
			return
		if Tags.Enchantment not in evt.spell.tags:
			return
		if self.spell.get_stat('pierce'):
			targets = [t for t in self.owner.level.get_units_in_ball(self.owner, evt.spell.range)]
			targets = [t for t in targets if self.owner.level.are_hostile(t, self.owner)]
		else:
			targets = self.owner.level.units
			targets = [t for t in targets if self.owner.level.are_hostile(t, self.owner)]
			targets = [t for t in targets if self.owner.level.can_see(t.x, t.y, self.owner.x, self.owner.y)]
		random.shuffle(targets)
		
		self.owner.shields += 1
		self.copying = True
		for i in range(self.spell.get_stat('num_targets')):
			if targets == []:
				return
			target = targets.pop()
			spell = type(evt.spell)()
			if self.spell.get_stat('selfish'):
				spell.caster = self.spell.caster
				spell.owner = self.spell.caster
				self.stat_holder = self.spell.caster
				evt.caster.level.act_cast(self.spell.owner, spell, target.x, target.y, pay_costs=False)
			else:
				spell.caster = self.owner
				spell.owner = self.owner
				spell.statholder = self.spell.owner
				evt.caster.level.act_cast(self.owner, spell, target.x, target.y, pay_costs=False)

			self.owner.level.queue_spell(self.reset())

	def reset(self):
		self.copying = False
		yield

class Glassworks(Buff):
	def __init__(self):
		Buff.__init__(self)
		self.name = "Glassworks"
		self.buff_type = BUFF_TYPE_NONE
		self.description = "Revives slain enemies as Glass Golems."
		self.global_triggers[EventOnDeath] = self.on_death
		
	def on_death(self, evt):
		if not are_hostile(evt.unit, self.owner):
			return
		if evt.damage_event:
			if evt.damage_event.source:
				if evt.damage_event.source.owner == self.owner:
					self.owner.level.queue_spell(self.revive_unit(Point(evt.unit.x, evt.unit.y),evt.unit.max_hp))
				
	def revive_unit(self, point, max_hp):
		if self.owner.level.tiles[point.x][point.y].is_chasm:
			unit = FairyGlass()
		else:
			unit = GlassGolem()
		unit.max_hp = max_hp
		self.summon(unit, point)
		yield

def IdolOfGlass():
	idol = Unit()
	idol.name = "Idol of Reflection"
	idol.asset = ["TcrsCustomModpack", "Units", "glass_idol"]
	idol.tags = [Tags.Construct, Tags.Glass]

	idol.max_hp = 50
	idol.shields = 2
	idol.flying = True
	idol.stationary = True

	return idol

class IdolOfReflection(Spell):
	def on_init(self):
		self.name = "Idol of Reflection"
		self.tags = [Tags.Conjuration, Tags.Enchantment, Tags.Metallic]
		self.level = 5
		self.asset = ["TcrsCustomModpack", "Icons", "glass_idol_icon"]
		
		self.max_charges = 1
		self.range = 4
		self.shields = 5
		self.minion_health = 1
		self.num_targets = 2
		
		self.must_target_empty = True

		self.upgrades['selfish'] = (1, 2, "Self Reflection", "The spells are cast by the wizard instead of the idol.")
		self.upgrades['pierce'] = (1, 2, "Piercing", "The reflected spell now ignores walls, but the unit must be within the spell's castable range from the idol to the unit.")
		self.upgrades['glass'] = (1, 4, "Glassworks", "Units killed by the idol are revived as glass golems when over floors and glass faeries when over chasms.")

	def get_description(self):
		return ("Summons an idol of reflection. The idol is a stationary flying unit which has [{shields}_SH:shields] and [{minion_health}_HP:minion_health].\n"
				"When you cast an [enchantment] spell at it, it recasts the spell at [{num_targets}:num_targets] random units in line of sight, and gains a shield.").format(**self.fmt_dict())

	def get_extra_examine_tooltips(self):
		return [self.spell_upgrades[0], self.spell_upgrades[1], self.spell_upgrades[2], GlassGolem(), FairyGlass()]

	def cast_instant(self, x, y):
		unit = IdolOfGlass()
		unit.max_hp = 3
		unit.shields = self.get_stat('shields')
		unit.apply_buff(Reflector(self))
		if self.get_stat('glass'):
			unit.apply_buff(Glassworks())
		self.summon(unit, Point(x,y))



class ObsidianDagger(Spell):
	def on_init(self):
		self.name = "Obsidian Dagger"
		self.tags = [Tags.Fire, Tags.Dark, Tags.Sorcery, Tags.Conjuration]
		self.level = 2
		self.max_charges = 13
		self.asset = ["TcrsCustomModpack", "Icons", "obsidian_dagger_icon"]

		self.damage = 33
		self.damage_types = [Tags.Fire]
		self.range = 1.5
		self.melee = True
		
		self.minion_health = 4
		self.minion_damage = 7
		self.minion_range = 5
		self.minion_duration = 7
		self.num_summons = 12

		self.can_target_self = True
		self.can_target_empty = False
		self.units_killed = []

		self.upgrades[('knife','num_targets','radius')] = ([1,2,5], 5, "Knife Juggler", "Also deals damage to [2:num_targets] random enemies within a [5:radius] tile radius in line of sight.")
		self.upgrades['glass'] = (1, 2, "Volcanic Glass", "Summoned ghosts are [glass], and glassify units on hit with their firebolt.")
		self.upgrades['ritual'] = (1, 1, "Ritual Dagger", "Each ally killed with the spell refunds the charge used.")

	def get_description(self):
		return ("Deals [{damage}_fire:fire] damage to target unit.\n"
				"Cast on yourself to summon a fire ghost for every non [undead] unit killed with this spell since the last summoning.\n"
				"Summon up to [{num_summons}:num_summons] ghosts."
				"Ghosts have [{minion_health}_hp:minion_health], a ranged fire attack, and last for [{minion_duration}_turns:minion_duration].").format(**self.fmt_dict())
	
	def cast_instant(self, x, y):
		if self.caster.x == x and self.caster.y == y:
			if self.units_killed == []:
				return
			for u in self.units_killed:
				unit = GhostFire()
				unit.name = u + " Ghost"
				if self.get_stat('glass'):
					unit.recolor_primary = Tags.Glass.color
					unit.tags.append(Tags.Glass)
					unit.spells[0].effect = Tags.Glassification
					unit.spells[0].buff_name = "Glassed"
					unit.spells[0].buff = GlassPetrifyBuff
					unit.spells[0].buff_duration = 1
				unit.turns_to_death = 7
				apply_minion_bonuses(self, unit)
				self.summon(unit,self.caster)
			self.units_killed = []
		else: 
			units = [self.caster.level.get_unit_at(x, y)]
			if units == []:
				return
			if self.get_stat('knife'):
				targets = [u for u in self.owner.level.get_units_in_ball(self.caster, self.get_stat('radius',base=5)) if u != units[0] ]
				targets = [u for u in targets if are_hostile(self.caster, u) and self.caster.level.can_see(u.x, u.y, self.caster.x, self.caster.y)]
				random.shuffle(targets)
				for i in range(self.get_stat('num_targets',base=2)):
					if targets == []:
						continue
					u = targets.pop()
					units.append(u)
			for unit in units:
				unit.deal_damage(self.get_stat('damage'), Tags.Fire, self)
				if not unit.is_alive() and Tags.Undead not in unit.tags:
					if len(self.units_killed) < self.get_stat('num_summons'):
						self.units_killed.append(unit.name)
					if self.get_stat('ritual') and not are_hostile(self.caster, unit):
						self.cur_charges += 1
						
				start = Point(self.caster.x, self.caster.y)
				end = Point(unit.x, unit.y)
				for p in self.caster.level.get_points_in_line(start, end)[1:]:
					self.caster.level.projectile_effect(p.x, p.y, proj_name='silver_spear', proj_origin=start, proj_dest=end)



class Furious(Buff):
	def __init__(self, spell):
		self.spell = spell
		Buff.__init__(self)
	def on_init(self):
		self.name = "Fury"
		self.color = Tags.Blood.color
		self.asset = ['status', 'darkness']
		self.global_triggers[EventOnDeath] = self.on_death
		self.damage = 1

	def on_advance(self):
		self.owner.deal_damage(self.damage, Tags.Dark, self.spell)
		self.owner.deal_damage(self.damage, Tags.Fire, self.spell)
		self.damage += 1

	def on_death(self, evt):
		if evt.unit == self.owner and self.spell.get_stat('death'):
			spell = self.spell.caster.get_or_make_spell(WheelOfFate)
			self.spell.caster.level.act_cast(self.spell.caster, spell, self.spell.caster.x, self.spell.caster.y, pay_costs=False)
		if distance(evt.unit, self.owner) <= 1.5:
			self.owner.remove_buff(self)

class WordofBlood(Spell):
	def on_init(self):
		self.name = "Word of Fury"
		self.tags = [Tags.Fire, Tags.Blood, Tags.Word]
		self.asset = ["TcrsCustomModpack", "Icons", "word_of_blood"]
		self.level = 7
		self.hp_cost = 45

		self.max_charges = 1
		self.range = 0
		self.duration = 10
		self.self_target = True

		self.upgrades['elemental'] = (1, 2, "Elemental's Wrath", "Also affects [Fire], [Ice], and [Lightning] units.")
		self.upgrades['death'] = (1, 7, "Death Drive", "When any unit with Fury dies, you cast wheel of death.", [Tags.Dark])
		self.upgrades['blind'] = (1, 3, "Blind Fury", "Blinds and Berserks all affected units for 1 turn on cast.", [Tags.Chaos])

	def get_description(self):
		return ("All [living] and [demon] units, including the wizard, gain Fury for [{duration}_turns:duration].\n"
				"Each unit with Fury takes 1 [dark] and [fire] damage each turn, increasing by 1 each turn.\n"
				"Fury is removed if any adjacent unit dies.\n").format(**self.fmt_dict())

	def get_extra_examine_tooltips(self):
		return [self.spell_upgrades[0], self.spell_upgrades[1], self.spell_upgrades[2]]

	def cast_instant(self, x, y):
		tags = [Tags.Living, Tags.Demon]
		if self.get_stat('elemental'):
			tags.extend( [Tags.Fire, Tags.Ice, Tags.Lightning] )
		units = [u for u in self.caster.level.units if any(tag in tags for tag in u.tags)]
		for unit in units:
			unit.apply_buff(Furious(self), self.get_stat('duration'))
			if self.get_stat('blind'):
				unit.apply_buff(BlindBuff(), 2)
				unit.apply_buff(BerserkBuff(), 2)
				


class SlimePriestGrowth(SlimeBuff):
	def __init__(self, spell=None):
		self.spell = spell
		Buff.__init__(self)
		self.description = "50%% chance to gain 7 hp and 7 max hp per turn.  Upon reaching double max HP, transform and stop gaining max hp."
		self.name = "Slime Growth"
		self.color = Tags.Slime.color
		self.spawner = GreenSlime
		self.spawner_name = 'slimes'
		self.growth_chance = 0.5

	def on_applied(self, owner):
		self.start_hp = self.owner.max_hp
		self.to_split = self.start_hp * 2
		self.growth = self.start_hp // 4
		self.description = "50%% chance to gain %d hp and max hp per turn.  Upon reaching %d HP,  transform and stop gaining max hp." % (self.growth, self.to_split)
		
	def on_advance(self):
		if random.random() < self.growth_chance:
			return
		if self.owner.has_buff(SlimeTransform):
			self.owner.deal_damage(-self.growth, Tags.Heal, self)
		else:
			if self.owner.cur_hp == self.owner.max_hp:
				self.owner.max_hp += self.growth
			self.owner.deal_damage(-self.growth, Tags.Heal, self)
			
		if self.owner.cur_hp >= self.to_split:
			duration = self.spell.get_stat('minion_duration')
			self.owner.apply_buff(SlimeTransform(self.spell), duration)
			self.owner.max_hp //= 2
			self.owner.cur_hp //= 2

class SlimeTransform(Buff):
	def __init__(self, spell=None):
		self.spell = spell
		Buff.__init__(self)
		
	def on_init(self):
		self.name = "Transformed"
		self.color = Tags.Slime.color
		self.buff_type = BUFF_TYPE_BLESS
		self.stack_type	= STACK_TYPE_TRANSFORM
		self.transform_asset = ["TcrsCustomModpack", "Units", "slimepriest_monster"]
		self.description = "Transform into a Slime"
		slimespew = SimpleRangedAttack(name="Slimy Spew",damage=self.spell.get_stat('minion_damage'), damage_type=Tags.Poison, radius=1, range=self.spell.get_stat('minion_range') )
		self.spells = [slimespew]

def SlimePriest(spell=None):
	unit = Unit()
	unit.name = "Slime Priest"
	unit.asset = ["TcrsCustomModpack", "Units", "slimepriest"]
	unit.tags = [Tags.Living, Tags.Holy, Tags.Slime]
	unit.max_hp = 36
	unit.resists[Tags.Poison] = 100
	unit.resists[Tags.Holy] = 100
	unit.resists[Tags.Physical] = 50
	
	if spell != None:
		unit.buffs.append(HealAuraBuff(5, spell.get_stat('radius')) )
	else:
		unit.buffs.append(HealAuraBuff(5,4) )
	unit.buffs.append(SlimePriestGrowth(spell))
	##unit.is_coward = True ##Work this into a different spell?
	return unit

def SlimePriestTooltip(spell=None):
	unit = Unit()
	unit.name = "Goo Priest"
	unit.asset = ["TcrsCustomModpack", "Units", "slimepriest_monster"]
	unit.tags = [Tags.Living, Tags.Holy, Tags.Slime]
	unit.max_hp = 36

	if spell:
		unit.buffs.append(HealAuraBuff(spell.get_stat('heal'),spell.get_stat('radius')))
	else:
		unit.buffs.append(HealAuraBuff(4, 4))
	unit.buffs.append(SlimePriestGrowth())
	unit.spells.append(SimpleRangedAttack(name="Slimy Spew",damage=10, damage_type=Tags.Poison, radius=1, range=3))
	return unit

class SlimePriestSpell(Spell):
	def on_init(self):
		self.name = "Goo Priest"
		self.tags = [Tags.Holy, Tags.Slime, Tags.Conjuration]
		self.level = 2
		self.asset = ["TcrsCustomModpack", "Icons", "goo_priest_icon"]

		self.max_charges = 3
		self.range = 5
		self.minion_health = 36
		self.minion_damage = 10
		self.minion_range = 3
		self.minion_duration = 20
		self.radius = 4
		self.heal = 4

		self.must_target_empty = True
		self.must_target_walkable = True
		
		self.upgrades[('hp_cost','bloody')] = ([30,1], 4, "Slimification", "The Goo priest can now cast your slimify spell on a 10 turn cooldown.", [Tags.Blood])
		self.upgrades['spider'] = (1, 3, "Spider Worship", "The Goo priest gains the [spider] tag and can summon [2:num_summons] spider allies on a 15 turn cooldown which last [20:minion_duration] turns.", [Tags.Nature])
		self.upgrades['cube'] = (1, 2, "Cubism", "Transforms into a [Fire], [Ice], or [Arcane] slime cube on death which lasts for [20:minion_duration] turns.")

	def get_description(self):
		return ("Summon a Goo Priest, which heals allies in a [{radius}_tiles:radius] radius for 4 hp, each turn.\n"
				"It has [{minion_health}_max_hp:minion_health] and has a 50% chance to gain max 25% of its max hp each turn.\n"
				"When it reaches twice its starting hp, it transforms and gains a ranged attack which deals [{minion_damage}_damage:poison] in a 1 tile radius."
				"Transformation Lasts [{minion_duration}_turns:minion_duration], and resets its hp.").format(**self.fmt_dict())

	def get_extra_examine_tooltips(self):
		return [SlimePriest(), SlimePriestTooltip(), self.spell_upgrades[0], self.spell_upgrades[1], self.spell_upgrades[2], RedSlimeCube(), IceSlimeCube(), VoidSlimeCube()]

	def cast(self, x, y):
		unit = SlimePriest(self)
		apply_minion_bonuses(self, unit)
		unit.turns_to_death = None
		if self.get_stat('spider'):
			unit.tags.append(Tags.Spider)
			def temp_spider():
				gs = GiantSpider()
				apply_minion_bonuses(self, gs)
				return gs
			unit.spells.append(SimpleSummon(spawn_func=temp_spider, num_summons=self.get_stat('num_summons',base=2), cool_down=15, duration=self.get_stat('minion_duration'), radius=5) )
		if self.get_stat('cube'):
			unit.buffs.append(RespawnAs( random.choice([RedSlimeCube, IceSlimeCube, VoidSlimeCube])))
		self.summon(unit,Point(x, y))
		
		if self.get_stat('bloody'):
			grant_minion_spell(Slimify, unit, self.caster)
		yield



class IronAngelEmpathy(Buff):
	def __init__(self, spell=None):
		self.spell = spell
		Buff.__init__(self)
	def on_init(self):
		self.name = "Thunderous Response"
		self.description = "Takes an extra turn when the wizard takes damage from any enemy source."
		self.color = Tags.Lightning.color
		self.global_triggers[EventOnDamaged] = self.on_damage

	def on_damage(self, evt):
		if not evt.unit.is_player_controlled:
			return
		self.owner.advance()

class IronAngelCompassion(Buff):
	def __init__(self, spell=None):
		Buff.__init__(self)
		self.spell = spell
		if self.spell != None:
			if self.spell.get_stat('cold'):
				self.owner_triggers[EventOnDeath] = self.on_death
				
	def on_init(self):
		self.name = "Pure Compassion"
		self.description = "Whenever another ally hurts an ally, despawn."
		self.color = Tags.Holy.color
		self.global_triggers[EventOnDamaged] = self.on_damage


	def on_damage(self, evt):
		if not evt.source:
			return
		if not evt.source.owner:
			return
		if type(evt.source) == Poison:
			return
		if evt.source.owner == self.owner:
			return
		if isinstance(evt.source, IronAngelCompassion):
			return
		if are_hostile(evt.source.owner, self.owner):
			if are_hostile(evt.source.owner, evt.unit) and self.spell.get_stat('venge'): 
				evt.source.owner.deal_damage(self.spell.get_stat('damage',base=8), Tags.Holy, self)
			return
		if not are_hostile(evt.source.owner, evt.unit):
			self.owner.kill(trigger_death_event=False)
			if not self.spell.get_stat('cold'):
				return
			spell = self.spell.caster.get_or_make_spell(SummonIcePhoenix)
			p = Point(self.owner.x, self.owner.y)
			self.spell.caster.level.act_cast(self.spell.caster, spell, p.x, p.y, pay_costs=False, queue=True)

	def on_death(self, evt):
		spell = self.spell.caster.get_or_make_spell(SummonIcePhoenix)
		p = Point(self.owner.x, self.owner.y)
		self.spell.caster.level.act_cast(self.spell.caster, spell, p.x, p.y, pay_costs=False, queue=True)

def CompassionAngel(spell=None):
	unit = Unit()
	unit.max_hp = 80
	unit.name = "Angel of Compassion"
	unit.asset = ["TcrsCustomModpack", "Units", "angel_of_compassion"]
	
	unit.tags = [Tags.Holy]
	unit.resists[Tags.Holy] = 100
	unit.flying = True

	unit.spells.append(SimpleMeleeAttack(damage=35,buff=Stun,buff_duration=1,damage_type=Tags.Holy,trample=True))
	unit.buffs.append(ReincarnationBuff(5))
	unit.buffs.append(IronAngelCompassion(spell))
	return unit

class SummonCompassionAngel(Spell):
	def on_init(self):
		self.name = "Angel of Compassion"
		self.tags = [Tags.Holy, Tags.Conjuration]
		self.level = 8
		self.asset = ["TcrsCustomModpack", "Icons", "angel_of_compassion_icon"]

		self.max_charges = 1
		self.range = 15
		self.minion_health = 80
		self.minion_damage = 35
		

		self.must_target_empty = True

		self.upgrades['cold'] = (1, 8, "Cool Headed", "Cast your Ice Phoenix spell at the angel's tile on both its death and despawning.", [Tags.Ice])
		self.upgrades['venge'] = (1, 8, "Fiery Vengeance", "Deal 8 [Fire] damage to any unit which damages its allies. This damage is fixed.", [Tags.Fire])
		self.upgrades['empathy'] = (1, 4, "Thunderous Response", "If you take any damage, the angel takes an extra turn.", [Tags.Lightning])

	def get_description(self):
		return ("Summons an angel of compassion.\nIt reincarnates up to 5 times, but despawns instantly if you or any ally deal damage to any other allied unit.").format(**self.fmt_dict())

	def get_extra_examine_tooltips(self):
		return [CompassionAngel(), self.spell_upgrades[0], self.spell_upgrades[1], self.spell_upgrades[2]]

	def cast(self, x, y):
		unit = CompassionAngel(self)
		if self.get_stat('empathy'):
			unit.apply_buff(IronAngelEmpathy(self))
		self.summon(unit,Point(x, y))
		yield


class Myopic(Upgrade):
	def on_init(self):
		self.level = 4
		self.name = "Myopic"
		self.description = "When a blind unit dies with no adjacent allies, it explodes."
	
	def on_advance(self):
		blind_u = [u for u in self.owner.level.units if u.has_buff(BlindBuff)]
		targets = [u for u in blind_u if are_hostile(self.owner, u)]


class OrbofBlindness(OrbSpell):
	def on_init(self):
		self.name = "Blinding Orb"
		self.tags = [Tags.Dark, Tags.Conjuration, Tags.Eye, Tags.Orb]
		self.level = 5
		self.asset = ["TcrsCustomModpack", "Icons", "orb_of_blindness"]
	
		self.max_charges = 6
		self.range = 9
		self.radius = 10
		self.damage = 40
		self.damage_type = [Tags.Dark]
		self.minion_health = 30
		self.shot_cooldown = 3
		self.num_targets = 3
		self.stats.append('shot_cooldown')
		self.requires_los = True
		self.must_target_empty = True
		self.cast_on_walls = False

		self.upgrades['myopic'] = (1, 3, "Myopic", "The blind effect stacks when applied to already blind units and increases with duration bonuses.")
		self.upgrades['orb_walk'] = (1, 3, "Translocatorb", "Target the orb to swap with it, as long as you can walk on its tile. Has a 75% chance to refund a charge.", [Tags.Translocation])
		self.upgrades['eye'] = (1, 5, "Eye-Orb Continuum", "Your orb becomes a mass of floating eyes at its expiration tile.")

	def get_description(self):
		return ("Summon an eye orb next to the caster, which blinds all units within [{radius}_tiles:radius] each turn for 2 turns.\n"
				"Every [{shot_cooldown}_turns:shot_cooldown] it deals [{damage}_dark:dark] damage to [{num_targets}_blind_enemies:num_targets] in line of sight.\n"
				"The orb has no will of its own, each turn it will float one tile towards the target."
				"The orb can be destroyed by [holy] damage.\nCan be cast while blind.").format(**self.fmt_dict())

	def get_extra_examine_tooltips(self):
		return [self.spell_upgrades[0], self.spell_upgrades[1], self.spell_upgrades[2], FloatingEyeMass()]

	def can_cast(self, x, y): ##Comical amount of overrides until I decide to make an anti-blind status effect (blindcasting was taken, maybe call it true-sight)
		caster = self.caster
		lvl = caster.level

		# dx/dy once
		dx = abs(caster.x - x)
		dy = abs(caster.y - y)

		# self targeting
		if not self.can_target_self and dx == 0 and dy == 0:
			return False

		# walkable
		if self.must_target_walkable and not lvl.can_walk(x, y):
			return False

		#range
		r = self.get_stat('range') + (caster.radius if self.melee else 0)
		if self.melee:
			if max(dx, dy) > (1 + caster.radius):
				return False
		else:
			if dx*dx + dy*dy > r*r:
				return False

		u = lvl.get_unit_at(x, y)

		# empty v occupied
		if not self.can_target_empty and not u:
			return False

		if self.must_target_empty and u:
			return False

		if not lvl.can_see(caster.x, caster.y, x, y, light_walls=False):
				return False

		return True

	def on_make_orb(self, orb):
		orb.name = "Blindeye Orb"
		orb.asset =  ["TcrsCustomModpack", "Units", "orb_of_sight"]
		orb.tags.append(Tags.Eye)
		orb.resists[Tags.Holy] = 0
		orb.max_hp = self.minion_health
		orb.count = self.get_stat('shot_cooldown') ##Super sketchy lol

	def on_orb_move(self, orb, next_point):
		targets = [u for u in orb.level.get_units_in_ball(orb, self.get_stat('radius')) if u != orb]
		for t in targets:
			b = t.get_buff(BlindBuff)
			if b == None:
				t.apply_buff(BlindBuff(), 2)
				orb.level.show_path_effect(orb, t, Tags.Physical, minor=False)
			else:
				b.turns_left = 2
		
		orb.count -= 1
		if orb.count <= 0:
			orb.count = self.get_stat('shot_cooldown')
			enemies = [t for t in targets if are_hostile(t, orb)]
			if enemies != []:
				random.shuffle(enemies)
			num_targets = self.get_stat('num_targets')
			if len(enemies) >= num_targets:
				blind_targets = enemies[:num_targets]
			else:
				blind_targets = enemies
			for e in blind_targets:
				for p in self.caster.level.get_points_in_line(orb, Point(e.x, e.y), find_clear=True)[1:-1]:
					self.caster.level.show_effect(p.x, p.y, Tags.Dark, minor=True)
				e.deal_damage(self.get_stat('damage'), Tags.Dark, self)

	def on_orb_walk(self, existing):
		x = existing.x
		y = existing.y
		if self.caster.level.can_move(self.caster, x, y, teleport=True, force_swap=True):
			self.caster.level.act_move(self.caster, x, y, teleport=True, force_swap=True)
			if random.randint(1,4) != 1:
				self.cur_charges += 1
		yield

	def on_orb_collide(self, orb, next_point):
		orb.level.show_effect(next_point.x, next_point.y, Tags.Dark)
		if self.get_stat('eye'):
			unit = FloatingEyeMass()
			apply_minion_bonuses(self, unit)
			self.summon(unit, next_point)
		yield



class VerminFormFlying(Buff):
	def __init__(self, spell):
		self.spell = spell
		Buff.__init__(self)

	def on_init(self):
		self.name = "Verminform"
		if self.spell.get_stat('vampire'):
			self.resists[Tags.Physical] = 100
			self.resists[Tags.Dark] = 100
			self.resists[Tags.Poison] = 100
			self.resists[Tags.Holy] = -100
			self.resists[Tags.Fire] = -100
			self.transform_asset = ["TcrsCustomModpack", "Units", "player_mist_form"]
		else:
			self.resists[Tags.Physical] = 75
			self.resists[Tags.Dark] = 75
			self.resists[Tags.Ice] = -50
			self.transform_asset = ["TcrsCustomModpack", "Units", "gristmage"]
			
		self.owner_triggers[EventOnDamaged] = self.on_dmg
		self.buff_type = BUFF_TYPE_BLESS
		self.stack_type = STACK_TYPE_TRANSFORM

		self.dmg_total = 0
		self.has_flying = False

	def on_dmg(self, evt):
		self.dmg_total += evt.damage
		while self.dmg_total >= 6:
			self.dmg_total -= 6
			if self.spell.get_stat('vampire'):
				unit = VampireMist()
			else:
				unit = FlyCloud()
			apply_minion_bonuses(self.spell, unit)
			self.spell.summon(unit, self.owner)

	def on_applied(self, owner): ##Should be no cases where flying is on the wizard, but  then this buff is removed and the flying becomes permanent.
		if self.owner.flying == True: ##There is a notable edge case where a temporary source of flying combined with this source of flying means that this buff won't provide flying if the temporary source ends early. But that's unavoidable.
			self.has_flying = True
		else:
			self.owner.flying = True

	def on_unapplied(self):
		if self.has_flying == False:
			self.owner.flying = False
		tile = self.owner.level.tiles[self.owner.x][self.owner.y]
		if tile.is_floor():
			return
		if tile.is_chasm and self.owner.flying == True:
			return

		tiles = []
		for p in self.owner.level.get_adjacent_points(self.owner, filter_walkable=True, check_unit=True):
			if self.owner.level.can_stand(p.x, p.y, self.owner, check_unit=True):
				tiles.append(p)
		if tiles != []:
			tile = random.choice(tiles)
			self.owner.level.act_move(self.owner, tile.x, tile.y, teleport=False)
			return

		possible_points = []
		for i in range(len(self.owner.level.tiles)):
			for j in range(len(self.owner.level.tiles[i])):
				if self.owner.level.can_stand(i, j, self.owner, check_unit=True):
					possible_points.append(Point(i, j))
		if not possible_points:
			self.owner.kill()
		tile = random.choice(possible_points)
		self.owner.level.act_move(self.owner, tile.x, tile.y, teleport=True)
		self.owner.apply_buff(Stun(), 5)

class VerminFormSpider(Buff):
	def __init__(self, spell):
		self.spell = spell
		Buff.__init__(self)

	def on_init(self):
		self.name = "Verminform"
		self.resists[Tags.Arcane] = 100
		self.resists[Tags.Physical] = 75
		self.resists[Tags.Ice] = -50
		self.transform_asset = ["TcrsCustomModpack", "Units", "player_spider_form"]
		self.buff_type = BUFF_TYPE_BLESS
		self.stack_type = STACK_TYPE_TRANSFORM

		self.is_spider = False

	def on_applied(self, owner):
		if Tags.Spider not in self.owner.tags:
			self.owner.tags.append(Tags.Spider)
			b = SpiderBuff()
			b.name = "Web weaver"
			b.color = Tags.Nature.color
			self.owner.apply_buff(b)
		else:
			self.is_spider = True

	def on_unapplied(self):
		if self.is_spider == False:
			if Tags.Spider in self.owner.tags: ##Edge case of buff being applied after being upgraded by before it runs out, so the wizard never had the tag, but it cannot be removed
				self.owner.tags.remove(Tags.Spider)
			self.owner.remove_buffs(SpiderBuff)

	def on_advance(self):
		tiles = self.spell.caster.level.iter_tiles()
		tiles_w = [t for t in tiles if type(self.spell.caster.level.tiles[t.x][t.y].cloud) == SpiderWeb]
		webs = [w for w in tiles_w if self.spell.caster.level.get_unit_at(w.x, w.y) == None and self.spell.caster.level.tiles[w.x][w.y].is_floor()]
		for i in range(self.spell.get_stat('num_summons',base=2)):
			if webs == []:
				break
			w = webs.pop(0)
			unit = PhaseSpider()
			apply_minion_bonuses(self.spell, unit)
			self.spell.summon(unit, w)

class VerminFormBurrow(Buff):
	def __init__(self, spell):
		self.spell = spell
		Buff.__init__(self)

	def on_init(self):
		self.name = "Verminform"
		self.resists[Tags.Physical] = 50
		self.resists[Tags.Fire] = 50
		self.resists[Tags.Lightning] = 50
		self.resists[Tags.Ice] = -50
		self.transform_asset = ["TcrsCustomModpack", "Units", "player_worm_form"]
		self.buff_type = BUFF_TYPE_BLESS
		self.stack_type = STACK_TYPE_TRANSFORM

		self.has_burrow = False

	def on_applied(self, owner):
		if self.has_burrow == False:
			if not type(self.owner.equipment.get(ITEM_SLOT_BOOTS)) == DrillShoes: ##Edge case of wearing drill shoes, THEN upgrading the spell with rockwurm causes burrowing loss. Can't fix other sources though.
				self.owner.burrowing = False

	def on_advance(self):
		tiles = self.owner.level.get_adjacent_points(self.owner, filter_walkable=False, check_unit=False)
		walls = [t for t in tiles if self.spell.caster.level.tiles[t.x][t.y].is_wall()]
		for w in walls:
			unit = random.choice([ RockWurm(), SkullWorm()])
			unit.turns_to_death = 21
			apply_minion_bonuses(self.spell, unit)
			self.owner.level.make_floor(w.x, w.y)
			self.spell.summon(unit, w)

	def on_unapplied(self):
		if self.has_burrow == False:
			if not type(self.owner.equipment.get(ITEM_SLOT_BOOTS)) == DrillShoes: ##Edge case of wearing drill shoes, THEN upgrading the spell with rockwurm causes burrowing loss. Can't fix other sources though.
				self.owner.burrowing = False

class Verminform(Spell):
	def on_init(self):
		self.name = "Verminform"
		self.tags = [Tags.Nature, Tags.Dark, Tags.Enchantment]
		self.level = 3
		self.asset = ["TcrsCustomModpack", "Icons", "verminform_icon"]
		
		self.max_charges = 3
		self.minion_health = 6
		self.minion_damage = 2
		self.duration = 10
		self.self_target = True
		self.range = 0

		self.upgrades['vampire'] = (1 ,3, "Shape of Mist",	"Become a vampiric mist with associated resistances.\n"
															"Instead of flies, vampiric mists split off, which turn into greater vampires.")
		self.upgrades[('spider','num_summons','minion_duration')] = ([1,2,6], 2, "Shape of Spider", "Become a web-spinning aether [spider] with associated resistances.\n"
															"Instead of flies, each turn [2:num_summons] empty webs becomes an aether spider, which last 6 turns.\nDoes not fly.", [Tags.Arcane, Tags.Conjuration])
		self.upgrades[('wurm','minion_duration')] = ([1,21], 5, "Shape of Worm", "Become a burrowing rockwurm with associated resistances.\n"
															"Instead of flies, each turn all adjacent walls transform into rockwurms or skullworms, which last 21 turns.\nDoes not fly.", [Tags.Conjuration])
	
	def get_description(self):
		return ("Transform into a fly swarm for [{duration}_turns:duration] turns.\n"
				"While you are transformed, you have flying, and fly swarm resists.\n"
				"For every 6 damage you take, a flycloud splits off.\n"
				"If you end the effect over a chasm, without flying, you teleport to a random tile and are stunned for 5 turns.").format(**self.fmt_dict())


	def get_extra_examine_tooltips(self):
		return [FlyCloud(), self.spell_upgrades[0], VampireMist(), self.spell_upgrades[1], PhaseSpider(), self.spell_upgrades[2], RockWurm(), SkullWorm()]

	def cast(self, x, y):
		if self.get_stat('spider'):
			buff = VerminFormSpider(self)
		elif self.get_stat('wurm'):
			buff = VerminFormBurrow(self)
		else:
			buff = VerminFormFlying(self)
		self.owner.apply_buff(buff, self.get_stat('duration'))
		yield



class RiftTremor(Spell): 
	def on_init(self):
		self.name = "Riftquake"
		self.tags = [Tags.Nature, Tags.Sorcery]
		self.level = 8
		self.asset = ["TcrsCustomModpack", "Icons", "riftquake_icon"]

		self.max_charges = 3
		self.damage = 40
		self.damage_type = [Tags.Physical]
		self.range = 0
		self.radius = 10
		self.num_targets = 4
		
		self.upgrades['shock'] = (1, 5, "Aftershocks", "Redeals 50% of the total damage from each rift's set of tremors, in one sum, to a random enemy unit as [lightning] damage.", [Tags.Lightning])
		self.upgrades['imp'] = (1, 6, "Imp-Tremors", "Tremors leave behind imps on tiles in their path. The imps summoned are the same as your Imp swarm spell, but last only 3 turns.", [Tags.Chaos])
		self.upgrades['slime'] = (1, 3, "Slimeshakes", "At the target of each tremor, cast your slimeshot", [Tags.Slime])
		#self.upgrades['shuffle'] = (1, 2, "Shuffle", "Shuffles the locations of the rifts to random walkable tiles.")
		
	def get_extra_examine_tooltips(self):
		return [self.spell_upgrades[0], EnergyKnight(), self.spell_upgrades[1], self.spell_upgrades[2]]

	def get_description(self):
		return ("Each rift sends out [{num_targets}_tremors:num_targets] targeting random enemies within [{radius}_tiles:radius].\n"
				"Each tremor deals [{damage}_physical_damage:physical] to all units along the ground on a path between target and the rift.").format(**self.fmt_dict())

	def get_impacted_tiles(self, x, y):
		gates = [tile.prop for tile in self.caster.level.iter_tiles() if isinstance(tile.prop, Portal)]
		points = []
		for gate in gates:
			ball = self.caster.level.get_points_in_ball(gate.x, gate.y, self.get_stat('radius'))
			for p in ball:
				points.append(p)
		return points

	def cast(self, x, y):
		##Variation of earthwrath, but I think adds a very cool dimension of planning around weird rift layouts.
		## As a consequence this spell is extremely powerful when you can hit your enemies, but it won't even work on mordred, which is kind of bad. Maybe if there are no portals just choose edge tiles.
		gates = [tile.prop for tile in self.caster.level.iter_tiles() if isinstance(tile.prop, Portal)]
		if self.get_stat('imp'):
			impgate = self.caster.get_or_make_spell(ImpGateSpell)
		for gate in gates:
			dmg_total = 0
			targets = self.caster.level.get_units_in_ball(gate, self.get_stat('radius'))
			if targets == []:
				continue
			random.shuffle(targets)
			num_targets = self.get_stat('num_targets')
			targets = targets[:num_targets]
			for u in targets:
				if not are_hostile(self.owner, u):
					continue
				dummy = Unit()
				path = self.caster.level.find_path(gate, u, dummy, pythonize=True, unit_penalty=0)
				if not path:
					continue
				for p in path:
					dmg_total += self.caster.level.deal_damage(p.x, p.y, self.get_stat('damage'), Tags.Physical, self)
					if self.get_stat('imp'):
						imp = random.choice(impgate.get_imp_choices())()
						imp.turns_to_death = 2
						self.summon(imp, p)
				if self.get_stat('slime'):
					spell = self.caster.get_or_make_spell(Slimeshot)
					self.caster.level.act_cast(self.caster, spell, p.x, p.y, pay_costs=False)
			if dmg_total > 2 and self.get_stat('shock'):
				vuln_units = [u for u in self.caster.level.units if u.resists[Tags.Lightning] < 100 and are_hostile(self.caster, u)]
				if vuln_units == []:
					continue
				targ = random.choice(vuln_units)
				targ.deal_damage(dmg_total // 2, Tags.Lightning, self)
					
		yield



class Transfusion(Buff):
	def __init__(self, spell):
		self.spell = spell
		Buff.__init__(self)

	def on_init(self):
		self.global_triggers[EventOnSpendHP] = self.spend_hp
		self.name = "Transfusion"
		self.color = Tags.Blood.color
		self.description = "When hp is spent on blood spells, gain that much max hp"
		self.bonus_hp = 20
		if self.spell.get_stat('fix'):
			self.spells.append( self.spell.caster.get_or_make_spell(Bonespear) )
		self.is_stationary = False
		if self.spell.get_stat('plant'): 
			pull_attack = PullAttack(damage=self.spell.get_stat('minion_damage',base=2), range=self.spell.get_stat('minion_range',base=10), color=Tags.Nature.color)
			pull_attack.name = "Vines"
			pull_attack.cool_down = 1
			self.spells = [pull_attack]
		
	def spend_hp(self, evt):
		self.bonus_hp += evt.hp
		self.owner.max_hp += evt.hp
		self.owner.cur_hp += evt.hp
		self.owner.level.show_path_effect(self.owner, evt.unit, Tags.Blood, minor=True)
		
	def on_applied(self, owner):
		if self.spell.get_stat('plant'):
			bonus_hp += self.spell.caster.max_hp // 2
			if self.owner.stationary == True:
				self.is_stationary = True
			else:
				self.owner.stationary = True
		self.owner.cur_hp += self.bonus_hp
		self.owner.max_hp += self.bonus_hp

	def on_unapplied(self):
		self.owner.max_hp -= self.bonus_hp
		if self.owner.cur_hp > self.owner.max_hp:
			self.owner.cur_hp = self.owner.max_hp
		self.spell.caster.deal_damage(self.bonus_hp * -1, Tags.Heal, self.spell)
		if self.is_stationary == False:
			self.owner.stationary = False

class BloodTransfusion(Spell):
	def on_init(self):
		self.name = "Transfusion"
		self.asset = ["TcrsCustomModpack", "Icons", "transfusion"]
		self.level = 2
		self.tags = [Tags.Enchantment, Tags.Blood]

		self.hp_cost = 20
		self.max_charges = 5
		self.range = 8
		self.duration = 20
		self.can_target_empty = False
		
		self.upgrades['form'] = (1, 5, "Transform", "The transfused unit becomes a random unit that could spawn in that realm.\nDoes not work on units which gain clarity.", [Tags.Chaos])
		self.upgrades['plant'] = (1, 4, "Transplant", "Pay an extra 10% of your max hp, to give the target 5 times that amount. The unit becomes a stationary [nature] unit, with a pulling vine attack.", [Tags.Nature])
		self.upgrades['fix'] = (1, 3, "Transfix", "The transfused unit gains your Bone Spear spell on a 3 turn cooldown.")

	def get_extra_examine_tooltips(self):
		return [self.spell_upgrades[0], self.spell_upgrades[1], self.spell_upgrades[2]]

	def get_description(self):
		return ("Target unit gains Transfusion for [{duration}_turns:duration].\nTransfusion gives 20 max hp, and whenever any unit spends hp to cast spells, transfusion gives them that much max hp.\n"
				"When transfusion ends, you heal for the max hp that the buff was giving.").format(**self.fmt_dict())


	def can_cast(self, x, y):
		unit = self.caster.level.get_unit_at(x, y)
		if unit:
			if are_hostile(self.caster, unit):
				return False
		return Spell.can_cast(self, x, y)

	def cast(self, x, y):
		target = self.caster.level.get_unit_at(x, y)
		if not target: 
			return
		if self.get_stat('plant'):
			cost = self.owner.max_hp // 10
			if self.owner.cur_hp > cost:
				self.caster.cur_hp -= cost
				self.caster.level.event_manager.raise_event(EventOnSpendHP(self.caster, cost), self.caster)
				
		if self.get_stat('form') and target.gets_clarity == False:
			team = target.team
			target.kill(trigger_death_event=False)
			tier = get_spawn_min_max(self.caster.level.level_no)[1]
			options = [(s, l) for s, l in spawn_options if l == tier]
			spawner = random.choice(options)[0]
			target = spawner()
			self.summon(target, Point(x, y),team=team)
			
		target.apply_buff(Transfusion(self), self.get_stat('duration'))
		yield



class FiredUp(Buff):
	def __init__(self, spell):
		self.spell = spell
		Buff.__init__(self)

	def on_init(self):
		self.name = "Fired Up!"
		self.color = Tags.Fire.color
		self.description = "Move up to 3 extra tiles."
		self.bonus_moves = 3
		self.owner_triggers[EventOnMoved] = self.on_move

	def on_move(self, evt): ## I like how this effect looks on units
		self.owner.level.show_effect(self.owner.x, self.owner.y, Tags.Translocation, minor=True)

	def on_pre_advance(self):
		self.owner.moves_left += self.bonus_moves

	def on_advance(self):
		if self.owner.moves_left > 0:
			self.owner.moves_left = 0

class SwiftWings(Upgrade):
	def on_init(self):
		self.level = 6
		self.name = "Swift Wings"
		self.description = ("Whenever any allied minion with flying is spawned, it gains fired up for [4:duration] turns.")
		self.global_triggers[EventOnUnitAdded] = self.on_enter

	def on_enter(self, evt):
		if evt.unit.flying == False:
			return
		if are_hostile(evt.unit, self.owner):
			return
		spell = self.owner.get_or_make_spell(FireEmUp)
		evt.unit.apply_buff(FiredUp(spell), spell.get_stat('duration'))

class FireEmUp(Spell):
	def on_init(self):
		self.name = "Fired Up"
		self.asset = ["TcrsCustomModpack", "Icons", "fire_em_up_icon"]
		self.level = 2
		self.tags = [Tags.Fire, Tags.Enchantment, Tags.Translocation]

		self.max_charges = 6
		self.range = 10
		self.duration = 4
		self.can_target_empty = False
		self.can_target_self = True
		
		self.add_upgrade(SwiftWings())
		self.upgrades['static'] = (1, 4, "Ecstatic", "Target gains a melee version of your overload spell, with a 3 turn cooldown.", [Tags.Lightning])
		self.upgrades['demon'] = (1, 2, "Demonic Rage", "Target becomes a [demon], and gains 10 stacks of bloodrage for [4:duration] turns, but if it wasn't already a [demon] it loses 20 life, to a minimum of 1.", [Tags.Chaos])

	def get_extra_examine_tooltips(self):
		return [self.spell_upgrades[0], self.spell_upgrades[1], self.spell_upgrades[2]]

	def get_description(self):
		return ("You or target allied unit gains Fired Up! for [{duration}_turns:duration].\nFired Up! grants up to 3 extra tiles of movement each turn, but only before casting a spell.").format(**self.fmt_dict())

	def can_cast(self, x, y):
		unit = self.caster.level.get_unit_at(x, y)
		if unit:
			if are_hostile(self.caster, unit):
				return False
		return Spell.can_cast(self, x, y)

	def cast(self, x, y):
		target = self.caster.level.get_unit_at(x, y)
		if not target: 
			return
		
		if self.get_stat('static'):
			spell = Overload()
			spell.caster = target
			spell.owner = target
			spell.statholder = self.caster
			spell.melee = True
			spell.range = 1
			spell.max_charges = 0
			spell.cool_down = 3
			target.add_spell(spell, prepend=True)
		
		if self.get_stat('demon'):
			if Tags.Demon in target.tags:
				if target.cur_hp > 20:
					target.cur_hp -= 20
				else:
					target.cur_hp = 1
			target.apply_buff(BloodrageBuff(10), self.get_stat('duration'))
			
		target.apply_buff(FiredUp(self), self.get_stat('duration'))
		yield


class ChainBolt(Spell):
	def on_init(self):
		self.name = "Chain Bolt"
		self.asset = ["TcrsCustomModpack", "Icons", "chain_bolt_icon"]
		self.tags = [Tags.Sorcery, Tags.Metallic]
		self.level = 2
		
		self.max_charges = 9
		self.damage = 17
		self.range = 12
		self.requires_los = False
		self.can_target_empty = False
		
		self.upgrades['split'] = (1, 1, "Master Splitter", "Each bolt gains 3 power when it splits, instead of losing it. If you strike yourself with a bolt, you only take 3 damage, and the bolt dgains 30 damage after splitting.")
		self.upgrades[('trick','duration')] = ([1,2], 4, "Trickshot", "If a splitting bolt traveled more than 4 tiles to hit its target, it also deals [arcane] damage and glassifies its target for [2:duration] turns.", [Tags.Arcane])
		self.upgrades['metal'] = (1, 3, "Metallurgy", "If you strike yourself with a bolt, you only take 3 damage and regain a charge of a different level 5 or below [fire] spell you know.", [Tags.Fire])

	def get_description(self):
		return ("Target unit takes [{damage}_physical_damage:physical], and then 4 bolts are sent in each direction, passing through walls and striking the first unit hit.\n"
				"Each bolt deals 3 less damage than the bolt it split from, and splits into 2 bolts which travel perpendicular, repeating the process."
				"\nDoes not split on large enemies.").format(**self.fmt_dict())

	def get_impacted_tiles(self, x, y):
		for i in range(-50, 50):
			yield Point(x+i, y)
			if i != 0:
				yield Point(x, y+i)

	def dir_bolt(self, x, y, dmg, x_mod, y_mod):
		first = Point(x, y)
		point = Point(x + x_mod, y + y_mod)
		unit = self.caster.level.get_unit_at(point.x, point.y)
		while unit == None and self.caster.level.is_point_in_bounds(point):
			temp_point = Point(point.x + x_mod, point.y + y_mod)
			unit = self.caster.level.get_unit_at(temp_point.x, temp_point.y)
			point = temp_point
			if unit != None:
				if unit.radius > 0:
					unit = None

		path = Bolt(self.caster.level, first, point, two_pass=False, find_clear=False)
		for p in path:
			self.owner.level.show_effect(p.x, p.y, Tags.Physical, minor=True)

		if unit != None:
			if self.get_stat('trick'):
				dist = distance(first, point)
				if dist >= 4:
					unit.deal_damage(dmg, Tags.Arcane, self)
					unit.apply_buff(GlassPetrifyBuff(), self.get_stat('duration',base=2))
			if unit.is_player_controlled:
				if self.get_stat('split'):
					dmg += 30
					unit.deal_damage(3, Tags.Physical, self)
				elif self.get_stat('metal'):
					unit.deal_damage(3, Tags.Physical, self)
					fire_spells = [s for s in self.caster.spells if Tags.Fire in s.tags and s.level <= 4 and s.cur_charges < s.get_stat('max_charges') and s != self]
					if fire_spells != []:
						s = random.choice(fire_spells)
						s.cur_charges += 1
				else:
					unit.deal_damage(dmg, Tags.Physical, self)
			else:
				unit.deal_damage(dmg, Tags.Physical, self)
				
			if self.get_stat('split'):
				dmg += 3
			else:
				dmg -= 3
			if dmg <= 0:
				return
			if x_mod == 0 and dmg > 0:
				self.dir_bolt(point.x, point.y, dmg, 1, 0)
				self.dir_bolt(point.x, point.y, dmg, -1, 0)
			elif y_mod == 0 and dmg > 0:
				self.dir_bolt(point.x, point.y, dmg, 0, 1)
				self.dir_bolt(point.x, point.y, dmg, 0, -1)

	def cast(self, x, y):
		dmg = self.get_stat('damage')
		self.caster.level.deal_damage(x, y, dmg, Tags.Physical, self)
		if self.get_stat('split'):
			dmg += 3
		else:
			dmg -= 3
		self.dir_bolt(x, y, dmg, 1, 0)
		self.dir_bolt(x, y, dmg, -1, 0)
		self.dir_bolt(x, y, dmg, 0, 1)
		self.dir_bolt(x, y, dmg, 0, -1)
		yield



class SpiritOrbAbsorbed(Buff):
	def __init__(self, spell):
		Buff.__init__(self)
		self.spell = spell
		self.tag_bonuses[Tags.Holy]['minion_health'] = 4
		self.tag_bonuses[Tags.Holy]['minion_duration'] = 1

	def on_init(self):
		self.name = "Spirit Absorption"
		self.stack_type = STACK_INTENSITY
		self.buff_type = BUFF_TYPE_BLESS
		self.color = Tags.Holy.color

class OrbAbsorb(Spell):
	def __init__(self, spell):
		self.spell = spell
		Spell.__init__(self)
	def on_init(self):
		self.name = "Merge"
		self.description = "Sacrifices itself, turning into a ghost. Must be adjacent to the wizard."
		self.range = 1.5
		self.melee = True
		self.can_target_self = True
		self.cool_down = 2

	def get_ai_target(self):
		units = [u for u in self.caster.level.get_units_in_ball(self.caster, 1, diag=True) if not are_hostile(u, self.caster) and u.is_player_controlled]
		if units:
			return units[0]
		else:
			return None

	def cast_instant(self, x, y):
		self.caster.level.queue_spell(self.spell.orb_ascend(self.caster))

class SpiritOrb(OrbSpell):
	def on_init(self):
		self.level = 4
		self.name = "Spirit Orb"
		self.asset = ["TcrsCustomModpack", "Icons", "spirit_orb_icon"]
		self.tags = [Tags.Holy, Tags.Orb, Tags.Conjuration]

		self.range = 10
		self.max_charges = 12
		
		self.minion_health = 40
		self.minion_damage = 4
		self.minion_duration = 23
		self.minion_range = 4
		
		self.can_target_empty = False
		self.cast_on_walls = False
		self.orb_walk = True

		self.upgrades[('aura','radius')] = ([1, 3], 2, "Path of Frost", "The orb gains a 2 damage [ice] aura with a [{radius}_tile:radius] radius.", [Tags.Ice])
		self.upgrades['empower'] = (1, 4, "Spirit Empowerment", "Each orb's ascension also grants your [holy] spells and skills 4 bonus minion health and 1 bonus minion duration, which lasts until the realm ends.")
		self.upgrades['modal'] = (1, 5, "Modal Soul", "Orbs gain the tags of the target. When an orb becomes a ghost, it applies a modifier corresponding one of its tags, e.g. [Fire] provides burning, [holy] provides immortal, etc.")

	def get_description(self):
		return ("Convert target enemy unit with less than or equal to [{minion_health}_current_hp:minion_health] into a spirit orb.\n"
				"The spirit orb drifts toward your location each turn, and can ascend into a ghost when adjacent to the wizard.\n"
				"The orb can be destroyed by [dark].\n"
				"Can be cast again on the orb to trigger the ascension instantly.").format(**self.fmt_dict())

	def get_extra_examine_tooltips(self):
		return [self.make_ghost(), self.spell_upgrades[0], self.spell_upgrades[1], self.spell_upgrades[2]]

	def can_cast(self, x, y):
		u = self.caster.level.get_unit_at(x, y)
		if not u:
			return False
		if self.get_orb(x, y):
			return True
		if u.cur_hp > self.get_stat('minion_health'):
			return False
		if not are_hostile(self.caster, u):
			return False

		return Spell.can_cast(self, x, y)

	def get_impacted_tiles(self, x, y):
		pather = Unit()
		pather.flying = True
		path = self.owner.level.find_path(self.owner, Point(x,y), pather, cosmetic=True,pythonize=True, unit_penalty=1)
		path_array = []
		for p in path:
			path_array.append(p)
		path = path_array
		if len(path) < 1:
			return []

		return path

	def orb_ascend(self,orb):
		unit = self.make_ghost()
		if self.get_stat('modal'):
			tagdict = ModConvertor()
			shuffle_tags = orb.tags
			random.shuffle(shuffle_tags)
			for t in shuffle_tags:
				if t in tagdict:
					modifier = tagdict[t]
					BossSpawns.apply_modifier(modifier, unit)
					break

		self.summon(unit,self.caster)
		if self.get_stat('empower'):
			self.caster.apply_buff(SpiritOrbAbsorbed(self))
			
		orb.kill()
		yield

	def cast(self, x, y):
		existing = self.get_orb(x, y)
		if existing:
			for r in self.on_orb_walk(existing):
				yield self.caster.level.queue_spell(self.orb_ascend(existing))
			return

		pather = Unit()
		pather.flying = True
		path = self.owner.level.find_path(self.owner, Point(x,y), pather, cosmetic=True,pythonize=True, unit_penalty=1)
		path_array = []
		for p in path:
			path_array.append(p)
		path = path_array
		if len(path) < 1:
			print('test')
			return
		
		start_point = path[-1]
		enemy = self.caster.level.get_unit_at(x, y)
		if enemy != None:
			if are_hostile(self.caster, enemy):
				enemy_tags = enemy.tags
				enemy.kill()
		else:
			enemy_tags = []
		unit = self.make_orb(len(path) + 1)
		if self.get_stat('modal'):
			for t in enemy_tags:
				if t not in unit.tags:
					unit.tags.append(t)
		buff = OrbBuff(spell=self, dest=Point(self.caster.x, self.caster.y))
		unit.spells.append(OrbAbsorb(self))
		unit.buffs.append(buff)
		if self.get_stat('aura'):
			dmg_aura = DamageAuraBuff(2,[Tags.Ice],self.get_stat('radius'))
			unit.buffs.append(dmg_aura)
		self.summon(unit, start_point)

	def on_orb_move(self, orb, next_point):
		pass

	def on_make_orb(self, orb):
		orb.tags.append(Tags.Holy)
		orb.asset =  ["TcrsCustomModpack", "Units", "spirit_orb"]
		orb.resists[Tags.Dark] = 0

	def make_ghost(self):
		unit = HolyGhost()
		unit.tags = [Tags.Holy]
		unit.name = "Spirit Remnant"
		unit.spells = [ SimpleRangedAttack(damage=self.get_stat('minion_damage'), damage_type=Tags.Holy, range=self.get_stat('minion_range')) ]
		apply_minion_bonuses(self, unit)
		return unit

	# def can_threaten_tile(self, orb, x, y):
	# 	return False # arcane orb buff doesn't do anything, threat comes from spell it knows

class OffGuard(Buff):
	def on_init(self):
		self.name = "Off-Guard"
		self.buff_type = BUFF_TYPE_CURSE
		self.stack_type = STACK_INTENSITY
		self.color = Tags.Physical.color
		self.resists[Tags.Physical] = -50
		self.resists[Tags.Poison] = -50

class SlimeRay(Spell):
	def on_init(self):
		self.level = 5
		self.name = "Sludge Spray"
		self.asset = ["TcrsCustomModpack", "Icons", "sludge_spray_icon"]
		self.tags = [Tags.Slime, Tags.Nature, Tags.Sorcery]
		self.damage_type = [Tags.Poison, Tags.Physical]
		
		self.max_charges = 12
		self.range = 6
		self.damage = 45
		self.angle = math.pi / 4

		self.upgrades[('raise','num_targets')] = ([1,3], 2, "Re-raise", "Up to [3:num_targets] slimes in the aoe gain the immortal modifier.", [Tags.Holy, Tags.Dark])
		self.upgrades['buff'] =  (1, 4, 'Bad Breath',	"Units have 2 random debuffs applied for 3 turns, even if they are immune to the damage." +
														"\nDebuffs have a 7/8 chance to be: Berserk, Fear, Frozen, Petrify, Poison, Silence, Stun, or 1/8 chance to be a random spell debuff from your Immolate, Deathchill, Slimify, or Seal Fate.", [Tags.Enchantment])
		self.upgrades[('offg', 'duration')] =  ([1,3], 3, 'Off-guard', 'Before dealing damage, applies a stacking debuff which reduces the [physical] and [poison] resistances of targets by 50% for [2:duration] turns.')

	def get_description(self):
		return ("Shoot a cone of sludge, dealing [{damage}:damage] [poison] or [physical] damage to affected units."
				"Consumes adjacent slimes to empower the spell with 1 range per slime.").format(**self.fmt_dict())

	def get_adjacent_slimes(self):
		slimes = []
		for p in self.caster.level.get_adjacent_points(self.caster, filter_walkable=False):
			adj_unit = self.caster.level.get_unit_at(p.x, p.y)
			if adj_unit == None:
				continue
			if Tags.Slime in adj_unit.tags:
				slimes.append(adj_unit)
		return slimes

	def aoe(self, x, y, bonus):
		target = Point(x, y)
		return Burst(self.caster.level, Point(self.caster.x, self.caster.y), self.get_stat('range') + bonus, burst_cone_params=BurstConeParams(target, self.angle))

	def get_impacted_tiles(self, x, y):
		bonus = len(self.get_adjacent_slimes())
		return [p for stage in self.aoe(x, y, bonus) for p in stage]

	def random_debuff(self, unit):
		def spell_debuff():
			pair = random.choice([ [ImmolateSpell, ImmolateBuff], [DeathChill, DeathChillDebuff], [Slimify, SlimifyBuff], [SealFate, SealedFateBuff] ])
			buff = pair[1](self.caster.get_or_make_spell(pair[0]))
			return buff
		
		buff_list = [BerserkBuff, FearBuff, FrozenBuff, PetrifyBuff, Poison, Silence, Stun, spell_debuff]
		for b in unit.buffs:
			if type(b) in buff_list:
				buff_list.remove(type(b))
		buff = random.choice(buff_list)
		unit.apply_buff(buff(), 3)
		

	def cast(self, x, y):
		slimes = self.get_adjacent_slimes()
		count = self.get_stat('num_targets')
		for stage in self.aoe(x, y, len(slimes)):
			for point in stage:
				if point.x == self.caster.x and point.y == self.caster.y:
					continue
				tag = random.choice([Tags.Poison, Tags.Physical])
				unit = self.caster.level.get_unit_at(point.x, point.y)
				if unit == None:
					self.caster.level.show_effect(point.x, point.y, tag, minor=True)
					continue
				if self.get_stat('offg'):
					unit.apply_buff(OffGuard(), self.get_stat('duration'))
				unit.deal_damage(self.get_stat('damage'), tag, self)
				if self.get_stat('raise'):
					if not are_hostile(self.caster, unit) and Tags.Slime in unit.tags:
						if count > 0:
							BossSpawns.apply_modifier(BossSpawns.Immortal, unit)
							count -= 1
				if self.get_stat('buff'):
					self.random_debuff(unit)
					self.random_debuff(unit)
	
		for u in slimes:
			self.caster.level.show_effect(u.x, u.y, Tags.Nature)
			u.kill()
		yield

class Championship(Buff):
	def __init__(self, spell):
		Buff.__init__(self)
		self.spell = spell
		self.bonus = 0

	def on_init(self):
		self.name = "Whitewolf Champion"
		self.stack_type = STACK_REPLACE
		self.buff_type = BUFF_TYPE_BLESS
		self.color = Tags.Nature.color

	def on_applied(self, owner):
		owner.cur_hp = owner.cur_hp * 3
		owner.max_hp = owner.max_hp * 3
		if self.owner.turns_to_death != None:
			owner.turns_to_death = (owner.turns_to_death * 3) + self.bonus
			
		has_leap = False
		for s in owner.spells:
			if type(s) == LeapAttack:
				has_leap = True
				if s.damage < self.spell.get_stat('minion_damage'):
					s.damage = self.spell.get_stat('minion_damage')
		if not has_leap:
			leap_spell = LeapAttack(self.spell.get_stat('minion_damage'), self.spell.get_stat('minion_range'),Tags.Physical, is_leap=True, is_ghost=True)
			leap_spell.name = "Leap Attack"
			owner.add_spell(leap_spell, prepend=True)
			
		has_summon = False
		for s in owner.spells:
			if s.name == "Summon Animals":
				has_summon = True
		if self.spell.get_stat('animal') and has_summon == False:
			summons = self.spell.get_stat('num_summons')
			duration = self.spell.get_stat('minion_duration')
			summon_spell = SimpleSummon(self.spell.make_animals, summons, 5, duration)
			summon_spell.name = "Summon Animals"
			summon_spell.description = "Summons %d bats, mantises, or snakes, for %d turns" % (summons, duration)
			owner.add_spell(summon_spell, prepend=True)
			
		if not self.spell.get_stat('sacrifice'):
			return
		for spell in self.owner.spells:
			if not hasattr(spell, 'damage'):
				continue
			spell.damage += self.bonus * 4
			
	def on_unapplied(self):
		owner = self.owner
		owner.cur_hp = owner.cur_hp / 3
		owner.max_hp = owner.max_hp / 3

class WolfChampion(Spell):
	def on_init(self):
		self.name = "Whitewolf Champion"
		self.tags = [Tags.Nature, Tags.Enchantment]
		self.level = 5
		self.asset = ["TcrsCustomModpack", "Icons", "whitewolf_icon"]
		
		self.max_charges = 1
		self.minion_damage = 30
		self.minion_range = 5
		self.range = 50
		
		self.can_target_empty = False
		self.requires_los = False

		self.upgrades[('animal','num_summons','minion_duration')] = ([1, 3, 5], 5, "Animalism", "The champion also learns a spell to summon 3 snakes, bats, or mantises randomly every 5 turns, which last for 5 turns.")
		self.upgrades[('fast', 'quick_cast')] = ([1,1], 2, "Celerity", "Casting Whitewolf Champion only takes half a turn.\nApplies the quickened modifier to the champion, if unmodified.")
		self.upgrades[('sacrifice','hp_cost')] = ([1,10], 4, "Potence", "Each ally destroyed by the spell provides the champion with 4 bonus damage to its spells, and 1 extra turn if temporary.", [Tags.Blood])
		
	def get_description(self):
		return ("Target ally's hp and remaining turns are tripled. It gains the [nature] tag, and a [{minion_damage}_damage:minion_damage] wall jumping leap attack with [{minion_range}_leap:minion_range].\n"
				"Instantly destroys all other allied units with the same name.").format(**self.fmt_dict())

	def can_cast(self, x, y):
		unit = self.caster.level.get_unit_at(x, y)
		if unit:
			if are_hostile(self.caster, unit) or unit.is_player_controlled:
				return False
			return Spell.can_cast(self, x, y)

	def make_animals(self):
		unit = random.choice([Snake(), Bat(), Mantis()])
		apply_minion_bonuses(self, unit)
		return unit

	def cast(self, x, y):
		unit = self.caster.level.get_unit_at(x, y)
		if unit:
			if Tags.Nature not in unit.tags:
				unit.tags.append(Tags.Nature)
			buff = Championship(self)
			units = [u for u in self.caster.level.units if u.name == unit.name and not are_hostile(self.caster, u) and u != unit]
			for u in units:
				u.kill()
				if self.get_stat('sacrifice'):
					buff.bonus += 1
					self.caster.level.show_effect(u.x, u.y, Tags.Blood)
				else:
					self.caster.level.show_effect(u.x, u.y, Tags.Nature)
			unit.apply_buff(buff)
			if self.get_stat('fast'):
				BossSpawns.apply_modifier(BossSpawns.Quickened, unit)
		yield


class CreepingChillDebuff(Buff):
	def __init__(self, spell):
		self.spell = spell
		Buff.__init__(self)

	def on_init(self):
		self.name = "Creeping Frost"
		self.color = Tags.Ice.color
		self.buff_type = BUFF_TYPE_CURSE
		self.owner_triggers[EventOnDeath] = self.on_death
		self.asset = ['status', 'deathchill']

	def on_advance(self):
		self.owner.deal_damage(self.spell.get_stat('damage'), Tags.Ice, self.spell)
		if self.spell.get_stat('fiery'):
			self.owner.deal_damage(self.spell.get_stat('minion_damage'), Tags.Fire, self.spell)
		if self.owner.has_buff(RespawnAs):
			if not self.owner.is_alive():
				self.owner.level.queue_spell(self.revive(self.turns_left, Point(self.owner.x, self.owner.y)))

	def on_death(self, evt):
		self.owner.level.queue_spell(self.revive(self.turns_left, Point(evt.unit.x, evt.unit.y)))

	def revive(self, turns_left, point):
		unit = self.spell.make_unit()
		unit.turns_to_death = turns_left - 1
		if unit.turns_to_death <= 0:
			return
		self.spell.summon(unit, point)
		if self.spell.get_stat('split'):
			slime = IceSlime()
			apply_minion_bonuses(self.spell, slime)
			self.spell.summon(slime,point)
		yield

class CreepingChillApply(Spell):
	def __init__(self, spell):
		self.spell = spell
		Spell.__init__(self)
		self.name = "Creeping Frost"
		self.damage = self.spell.get_stat('damage')
		self.description = "Afflicts target enemy with creeping frost, which summons a new elemental if the target dies."

	def can_cast(self, x, y):
		unit = self.caster.level.get_unit_at(x, y)
		if not unit:
			return False
		if unit:
			if unit.has_buff(CreepingChillDebuff):
				return False
		return Spell.can_cast(self, x, y)

	def cast_instant(self, x, y):
		unit = self.caster.level.get_unit_at(x, y)
		if unit:
			buff = CreepingChillDebuff(self.spell)
			if self.owner.turns_to_death == None:
				unit.apply_buff(buff)
				if self.spell.get_stat('rage'):
					unit.apply_buff(BerserkBuff())
			else:
				unit.apply_buff(buff, self.owner.turns_to_death)
				if self.spell.get_stat('rage'):
					unit.apply_buff(BerserkBuff(), self.owner.turns_to_death)
			for p in self.caster.level.get_points_in_line(self.caster, Point(x, y)):
				self.caster.level.show_effect(p.x, p.y, Tags.Ice, minor=True)
			self.caster.kill()

def CreepingFrostElemental():
	unit = Unit()
	unit.max_hp = 50
	unit.name = "Frost Elemental"
	unit.asset = ["TcrsCustomModpack", "Units", "creeping_frost"]

	unit.tags = [Tags.Ice, Tags.Elemental]
	
	unit.resists[Tags.Ice] = 100
	unit.resists[Tags.Fire] = -100
	return unit

class CreepingFrost(Spell):
	def on_init(self):
		self.name = "Creeping Frost"
		self.range = 3
		self.max_charges = 1
		self.tags = [Tags.Ice, Tags.Conjuration, Tags.Enchantment]
		self.level = 5

		self.damage = 16
		self.minion_health = 40
		self.minion_range = 3
		self.minion_duration = 28

		self.can_target_empty = False

		self.upgrades[('fiery','minion_damage')] = ([1,16], 3, "Frostburn", "The debuff also deals [fire] damage, scaling with the [minion damage] stat instead minion damage.", [Tags.Fire])
		self.upgrades['split'] = (1, 2, "Budding", "When the target dies, also spawn an ice slime, which lasts for [28:minion_duration] turns.", [Tags.Slime])
		self.upgrades['rage'] = (1, 2, "Rage Virus", "The target is berserked for the same duration as creeping frost.", [Tags.Chaos])

	def make_unit(self):
		u = CreepingFrostElemental()
		u.spells.append(CreepingChillApply(self))
		apply_minion_bonuses(self, u)
		return u

	def cast_instant(self, x, y):
		unit = self.caster.level.get_unit_at(x, y)
		if unit:
			buff = CreepingChillDebuff(self)
			unit.apply_buff(buff, self.get_stat('minion_duration'))
			if self.get_stat('rage'):
				unit.apply_buff(BerserkBuff(), self.get_stat('minion_duration'))
			for p in self.caster.level.get_points_in_line(self.caster, Point(x, y)):
				self.caster.level.show_effect(p.x, p.y, Tags.Ice, minor=True)

	def get_description(self):
		return ("Target unit takes [{damage}_ice_damage:ice], each turn, for [{minion_duration}_turns:minion_duration], increasing with minion duration.\n"
				"If the target dies, it becomes a frost elemental, with [{minion_health}_max_hp:minion_health], and lasts for the remaining duration of the debuff.\n"
				"The elemental can reapply creeping frost for as many turns as the elemental has left, which sacrifices it in the process.").format(**self.fmt_dict())

	def get_extra_examine_tooltips(self):
		return [self.make_unit(), self.spell_upgrades[0], self.spell_upgrades[0], IceSlime(), self.spell_upgrades[2]]



class Trebuchet_Prop(Prop):
	def __init__(self, spell, x, y):
		self.spell = spell
		self.point = Point(x, y)
		self.name = "Trebuchet"
		self.asset = ['tiles', 'shrine', 'energy']
		self.count = 10
		self.launches = 0

	def advance(self):
		self.count -= 1
		if self.count <= 0:
			self.spell.owner.level.remove_obj(self)
			if self.launches >= 4 and self.spell.get_stat('flies'):
				spell = self.spell.caster.get_or_make_spell(Grist)
				self.spell.caster.level.act_cast(self.spell.caster, spell, self.point.x, self.point.y, pay_costs=False)
			return

		wizard = None
		walls = []
		chasms = []
		units = []
		for p in self.spell.owner.level.get_adjacent_points(self.point, filter_walkable=False):
			if self.spell.owner.level.tiles[p.x][p.y].is_wall():
				walls.append(p)
			if self.spell.get_stat('void') and self.spell.owner.level.tiles[p.x][p.y].is_chasm:
				chasms.append(p)
			unit = self.spell.owner.level.get_unit_at(p.x, p.y)
			if unit == None:
				continue
			if unit.name == "Wizard":
				wizard = unit
			elif not are_hostile(self.spell.owner, unit) and self.spell.get_stat('gnome'):
				units.append(unit)
		if wizard == None and not self.spell.get_stat('void'):
			return

		targets = [u for u in self.spell.owner.level.units if are_hostile(u, self.spell.owner) and (u.resists[Tags.Physical] < 100) and distance(u,wizard) >= 3]
		if targets  == []:
			return
		target = random.choice(targets)
		if len(units) > 0:
			unit = random.choice(units)
			unit.kill()
		elif len(walls) > 0:
			self.spell.owner.level.make_floor(walls[0].x, walls[0].y)
			self.spell.owner.level.show_effect(walls[0].x, walls[0].y, Tags.Translocation, minor=True)
		elif len(chasms) > 0:
			self.spell.owner.level.make_floor(chasms[0].x, chasms[0].y)
			self.spell.owner.level.show_effect(chasms[0].x, chasms[0].y, Tags.Translocation, minor=True)
		else:
			return

		spell = SimpleRangedAttack(name="Trebuchet", damage=self.spell.get_stat('damage'), range=50, radius=self.spell.get_stat('radius'), damage_type=Tags.Physical, proj_name='physical_ball')
		spell.owner = self.spell.owner
		spell.caster = self.spell.owner
		spell.tags = self.spell.tags
		spell.level = 3
		self.launches += 1
		wizard.level.act_cast(wizard, spell, target.x, target.y, pay_costs=False)


## TODO - This cool version - "Place a ballista on target empty tile. If the wizard stands beside the ballista, it fires a piercing shot in the opposite direction each turn."
class Trebuchet(Spell):
	def on_init(self):
		self.name = "Trebuchet"
		self.tags = [Tags.Metallic, Tags.Enchantment]
		self.level = 3
		self.max_charges = 3

		self.damage = 25
		self.radius = 2
		self.duration = 10
		
		self.must_target_empty = True
		self.must_target_walkable = True

		self.upgrades['flies'] = (1, 5, "Flying Machine", "If the catapult launched at least 4 tiles, when it expires cast your gristmage on its tile.", [Tags.Nature])
		self.upgrades['gnome'] = (1, 4, "Gnomish Machine", "Allies can now be consumed by the catapult just like walls are. This kills the unit instantly.", [Tags.Nature])
		self.upgrades['void'] = (1, 2, "Void Machine", "Chasms can now be consumed by the catapult just like walls are. The catapult operates even if the wizard is not adjacent.", [Tags.Arcane])

	def get_description(self):
		return ("Place a catapult on target empty tile\n. Each turn, if the wizard is adjacent, the catapult destroys one adjacent wall and targets a random enemy."
				"It deals [{damage}:damage] [physical] damage in a [{radius}_tile:radius] burst."
				"Won't target enemies within 3 tiles. Despawns after 10 turns.").format(**self.fmt_dict())

	def get_extra_examine_tooltips(self):
		return [] + self.spell_upgrades

	def can_cast(self, x, y):
		tile = self.caster.level.tiles[x][y]
		return not tile.prop and Spell.can_cast(self, x, y)

	def cast(self, x, y):
		prop = Trebuchet_Prop(self, x, y)
		self.owner.level.add_prop(prop, x, y)
		yield



class GrimeDissolving(Buff):
	def __init__(self, spell):
		self.spell = spell
		Buff.__init__(self)

	def on_init(self):
		self.name = "Grimy Dissolution"
		self.color = Tags.Slime.color
		self.buff_type = BUFF_TYPE_CURSE
		self.asset = ["TcrsCustomModpack", "Misc", "dissolution_debuff"]

	def on_advance(self):
		dmg = self.owner.deal_damage(self.spell.get_stat('damage'), Tags.Arcane, self.spell)
		for p in self.owner.level.get_points_in_line(self.owner, self.spell.caster):
			self.owner.level.show_effect(p.x, p.y, Tags.Nature, minor=True)
		self.spell.hp_bonus += dmg // 2
		if self.spell.hp_bonus >= self.spell.hp_max:
			self.spell.hp_bonus = self.spell.hp_max
		self.spell.update_desc()

class GrimeBuffing(Buff):
	def __init__(self, spell):
		self.spell = spell
		self.bonus = self.spell.hp_bonus
		Buff.__init__(self)

	def on_init(self):
		self.name = "Grimy Coating"
		self.color = Tags.Slime.color
		self.buff_type = BUFF_TYPE_BLESS
		self.asset = ["TcrsCustomModpack", "Misc", "dissolution_buff"]
	
	def on_applied(self, owner):
		owner.cur_hp += self.bonus
		owner.max_hp += self.bonus
		if not self.spell.get_stat('empower'):
			return
		tags = [Tags.Living, Tags.Slime]
		if any(owner.tags and tags):
			for s in owner.spells:
				if hasattr(s, 'damage'):
					s.damage += self.bonus // 10

class Biodegradation(Upgrade):
	def __init__(self, spell):
		self.spell = spell
		Upgrade.__init__(self)

	def on_init(self):
		self.level = 1
		self.name = "Biodegradation"
		self.description = "Whenever any [living] or [slime] unit dies, gain 5 hp bonus for your next cast on an ally."
		self.global_triggers[EventOnDeath] = self.on_death

	def on_death(self, evt):
		if Tags.Living in evt.unit.tags or Tags.Slime in evt.unit.tags:
			self.spell.hp_bonus += 5
			if self.spell.hp_bonus >= self.spell.hp_max:
				self.spell.hp_bonus = self.spell.hp_max
			self.spell.update_desc()

class Dissolution(Spell):
	def on_init(self):
		self.name = "Grimy Dissolution"
		self.tags = [Tags.Arcane, Tags.Slime, Tags.Enchantment]
		self.asset = ["TcrsCustomModpack", "Icons", "dissolution_icon"]
		self.level = 2

		self.range = 8
		self.max_charges = 8
		self.damage = 6
		self.duration = 10
		self.hp_bonus = 0
		self.hp_max = 150
		self.can_target_empty = False

		self.upgrades[('empower', 'hp_cost')] = ([1,3], 3, "Power Coating", "When cast on [living], or [slime] allies, grants their spells bonus damage equal to 10% of the hp bonus.", [Tags.Blood])
		self.upgrades['queen'] = (1, 6, "Queen's Court", "If the hp bonus is at 150 when you cast this spell, also summon a greater swamp queen beside the wizard, which lasts [30:minion_duration] turns.", [Tags.Nature, Tags.Conjuration])
		self.add_upgrade(Biodegradation(self))

		self.description = ("Target enemy unit takes [{damage}_arcane_damage:arcane] each turn, for [{duration}_turns:duration].\n"
				"Half of the damage dealt by this spell is stored as HP Bonus, up to 150.\nCast it on an ally to grant it maximum hp equal to the HP Bonus.\n"
				"HP Bonus: %d" % self.hp_bonus).format(**self.fmt_dict())
		
	def update_desc(self):
		self.description = ("Target enemy unit takes [{damage}_arcane_damage:arcane] each turn, for [{duration}_turns:duration].\n"
				"Half of the damage dealt by this spell is stored as HP Bonus, up to 150.\nCast it on an ally to grant it maximum hp equal to the HP Bonus.\n"
				"HP Bonus: %d" % self.hp_bonus).format(**self.fmt_dict())

	def get_description(self):
		return self.description

	def get_extra_examine_tooltips(self):
		return [self.spell_upgrades[0], self.spell_upgrades[1], self.make_unit(), self.spell_upgrades[2]]

	def cast(self, x, y):
		unit = self.caster.level.get_unit_at(x, y)
		if unit:
			if are_hostile(self.caster, unit):
				buff = GrimeDissolving(self)
				unit.apply_buff(buff, self.get_stat('duration'))
			else:
				buff = GrimeBuffing(self)
				if self.get_stat('queen') and self.hp_bonus >= self.spell.hp_max:
					queen = self.make_unit()
					queen.turns_to_death = 30
					apply_minion_bonuses(self, queen)
					self.summon(queen, self.caster)
				unit.apply_buff(buff)
				self.hp_bonus = 0
				self.update_desc()
		yield

	def make_unit(self):
		unit = SwampQueen()
		def mushboom():
			mushboom = random.choice([GreyMushboom(), GreenMushboom(), GlassMushboom(), RedMushboom()])
			mushboom.max_hp = 11
			apply_minion_bonuses(self, mushboom)
			return mushboom
		mushbooms = SimpleSummon(mushboom, num_summons=self.get_stat('num_summons',base=5), cool_down=12)
		mushbooms.name = "Grow Mushbooms"
		mushbooms.description = "Summons %d grey, green, glass, or red mushbooms nearby." % self.get_stat('num_summons',base=5)

		def plants():
			plant = FlyTrap()
			apply_minion_bonuses(self, plant)
			return plant
		flytraps = SimpleSummon(plants, num_summons=self.get_stat('num_summons',base=2), global_summon=True, cool_down=9, duration=20)
		flytraps.name = "Grow Plants"
		flytraps.description = "Summons %d flytraps at random locations, which last 20 turns." % self.get_stat('num_summons',base=2)

		heal = HealAlly(heal=self.get_stat('minion_damage',base=18), range=self.get_stat('minion_range',base=9))
		heal.cool_down = 5
		gaze = SimpleRangedAttack(damage=self.get_stat('minion_damage',base=1), damage_type=Tags.Poison, buff=Poison, buff_duration=self.get_stat('duration',base=10), range=self.get_stat('minion_range',base=14), cool_down=3)
		gaze.name = "Toxic Gaze"

		healaura = WizardHealAura(heal=1, duration=7, cool_down=12, radius=self.get_stat('radius',base=10))
		unit.spells = [mushbooms, flytraps, healaura, gaze]
		
		return unit



class AstraVirtue_Isolation(Upgrade):
	def __init__(self, spell):
		Upgrade.__init__(self)
		self.spell = spell

	def on_init(self):
		self.name = "Isolation"
		self.spell_bonuses[AstraVirtue]['range'] = 5
		self.description = "This spell recharges instantly if there are no units on any surrounding tiles as your turn ends."
		self.level = 1
		
	def on_advance(self):
		allies = []
		for p in self.owner.level.get_adjacent_points(self.owner, filter_walkable=False):
			unit = self.owner.level.get_unit_at(p.x, p.y)
			if unit == None:
				continue
			if self.owner == unit:
				continue
			allies.append(unit)
		if allies == []:
			self.owner.cool_downs[self.spell] = 0

class AstraVirtue_Vengeance(Upgrade):
	def __init__(self, spell):
		Upgrade.__init__(self)
		self.spell = spell

	def on_init(self):
		self.name = "Vengeance"
		self.spell_bonuses[AstraVirtue]['damage'] = 10
		self.description = "This spell recharges instantly when an ally dies. You automatically cast it for free, on one random enemy in range, if 2 or more allies died that turn."
		self.level = 2
		self.global_triggers[EventOnDeath] = self.on_death
		self.triggers = 0

	def on_pre_advance(self):
		self.triggers = 0

	def on_death(self, evt):
		if are_hostile(evt.unit, self.owner):
			return
		self.triggers += 1
		self.owner.cool_downs[self.spell] = 0
		if self.triggers == 2:
			spell = self.spell
			units = self.owner.level.get_units_in_ball(self.owner, self.spell.get_stat('range'))
			hostiles = [u for u in units if are_hostile(self.owner, u)]
			if hostiles == []:
				return
			target = random.choice(hostiles)
			self.owner.level.act_cast(self.owner, spell, target.x, target.y, pay_costs=False)

class AstraVirtue_Vitality(Upgrade):
	def __init__(self, spell):
		Upgrade.__init__(self)
		self.spell = spell

	def on_init(self):
		self.name = "Vitality"
		self.spell_bonuses_pct[AstraVirtue]['hp_cost'] = -100
		self.description = "This spell instantly recharges when you are healed. You automatically cast it for free, on one random enemy in range, when you get healed to max life."
		self.level = 1
		self.owner_triggers[EventOnHealed] = self.on_heal
		
	def on_heal(self, evt):
		self.owner.cool_downs[self.spell] = 0
		if self.owner.cur_hp == self.owner.max_hp:
			spell = self.spell
			units = self.owner.level.get_units_in_ball(self.owner, self.spell.get_stat('range'))
			hostiles = [u for u in units if are_hostile(self.owner, u)]
			if hostiles == []:
				return
			target = random.choice(hostiles)
			self.owner.level.act_cast(self.owner, spell, target.x, target.y, pay_costs=False)

class AstraVirtue_Blindsight(Upgrade):
	def __init__(self, spell):
		Upgrade.__init__(self)
		self.spell = spell

	def on_init(self):
		self.name = "Insight"
		self.spell_bonuses[AstraVirtue]['hp_cost'] = 4
		self.spell_bonuses[AstraVirtue]['requires_los'] = -1
		self.description = "This spell instantly recharges when you cast any spell on an enemy outside of your line of sight."
		self.level = 3
		##TODO implement


class AstraVirtue(Spell):
	def on_init(self):
		self.name = "Sacred Strike"
		self.level = 1
		self.tags = [Tags.Sorcery, Tags.Blood, Tags.Holy]
		self.asset = ["TcrsCustomModpack", "Icons", "sacred_strike_icon"]
		self.range = 9

		self.hp_cost = 2
		self.cool_down = 3
		self.damage = 15
		
		self.add_upgrade(AstraVirtue_Isolation(self))
		self.add_upgrade(AstraVirtue_Vitality(self))
		self.add_upgrade(AstraVirtue_Vengeance(self))
		self.add_upgrade(AstraVirtue_Blindsight(self))

		self.cast_on_walls = False
		self.can_target_empty = False

	def get_description(self):
		return ("Deal [{damage}_holy:holy] damage to target enemy, and [{damage}_physical:physical] to all adjacent enemies. This spell has a 3 turn cooldown.").format(**self.fmt_dict())

	def cast(self, x, y):
		unit = self.caster.level.get_unit_at(x, y)
		if unit:
			self.caster.level.deal_damage(unit.x, unit.y, self.get_stat('damage'), Tags.Holy, self)
			for p in self.caster.level.get_adjacent_points(Point(x,y), filter_walkable=False):
				adj_unit = self.caster.level.get_unit_at(p.x, p.y)
				if adj_unit == None:
					self.caster.level.show_effect(p.x, p.y, Tags.Physical, minor=True)
					continue
				if not are_hostile(adj_unit, self.caster):
					continue
				self.caster.level.deal_damage(adj_unit.x, adj_unit.y, self.get_stat('damage'), Tags.Physical, self)
		yield



class AdaptivePulse(Spell):
	def on_init(self):
		self.name = "Adaptive Pulse"
		self.level = 6
		self.tags = [Tags.Chaos, Tags.Sorcery]
		self.asset = ["TcrsCustomModpack", "Icons", "adaptive_pulse_icon"]
		self.range = 8
		self.max_charges = 8

		self.radius = 0
		self.damage = 80
		self.damage_thres = 120
		self.num_targets = 1

		self.cast_on_walls = False

		self.upgrades['radius'] = (4, 1, "Burst", "This spell explodes with [poison] damage at the target tile dealing damage in a [4:radius] tile burst."
			"\nThe burst happens if you gain radius from any source, even without this upgrade.\nThis spell's base radius is 0.", [Tags.Nature])
		self.upgrades['damage'] = (40, 3, "Damage", "The beam damages targets beside the beam, dealing [dark] damage."
			"\nThe secondary area happens if this spell has over %d damage from any source, even without this upgrade."%self.damage_thres, [Tags.Dark])
		self.upgrades['quick_cast'] = (1, 3, "Speed", "The target tile takes an additional hit of [fire] damage."
			"\nThe hit happens if this spell has quick cast from any source, even without this upgrade.", [Tags.Fire])
		self.upgrades['range'] = (8, 4, "Range", "The caster explodes with [holy] damage in a 4 tile burst, if the targeted tile is more than 14 tiles away."
			"\nThe burst happens if the tile is far away enough, even without this upgrade.", [Tags.Holy])
		self.upgrades['requires_los'] = (-1, 5, "Blindcasting", "The spell passes through walls."
			"\nThis happens if the spell has blindcasting from any source, even without this upgrade.", [Tags.Arcane])
		self.upgrades['num_targets'] = (3, 7, "Multibeam", "This spell also shoots out [3:num_targets] [lightning] beams to random enemies within line of sight, which deal 50% of the main beam's damage."
			"\nThe beams happens if this spell has 3 or more num targets, even without this upgrade.\nThis spell's base num targets is 1.", [Tags.Lightning])

	def get_description(self):
		return ("Deal [{damage}_physical:physical] damage in a beam.\nThis spell's upgrades have unique activation conditions.").format(**self.fmt_dict())

	def get_center_beam(self, x, y):
		if self.get_stat('requires_los'):
			beam = self.caster.level.get_points_in_line(self.caster, Point(x, y), find_clear=True)[1:]
		else:
			beam = self.caster.level.get_points_in_line(self.caster, Point(x, y), two_pass=False, find_clear=False)[1:]
		return beam

	def get_adj_beam(self, x, y):
		side_beam = []
		beam = self.get_center_beam(x, y)
		for p in beam:
			for q in self.caster.level.get_points_in_ball(p.x, p.y, 1.5):
				if q.x == self.caster.x and q.y == self.caster.y:
					continue
				if self.get_stat('damage') < self.damage_thres:
					continue
				if q not in beam and q not in side_beam:
					side_beam.append(q)
		return side_beam

	def get_target_burst(self, x, y):
		poison_burst = []
		if self.get_stat('radius') >= 1:
			if self.get_stat('requires_los'):
				poison_burst = [p for stage in Burst(self.caster.level, Point(x, y), self.get_stat('radius')) for p in stage]
			else:
				poison_burst = [p for stage in Burst(self.caster.level, Point(x, y), self.get_stat('radius'), ignore_walls=True) for p in stage]
		return poison_burst

	def get_caster_burst(self, x, y):
		holy_burst = []
		if distance(Point(self.caster.x, self.caster.y), Point(x, y)) >= 14:
			if self.get_stat('requires_los'):
				holy_burst = [p for stage in Burst(self.caster.level, self.caster, self.get_stat('radius',base=4)) for p in stage]
			else:
				holy_burst = [p for stage in Burst(self.caster.level, self.caster, self.get_stat('radius',base=4),ignore_walls=True) for p in stage]
		return holy_burst

	def get_impacted_tiles(self, x, y):
		return self.get_center_beam(x, y) + self.get_adj_beam(x, y) + self.get_target_burst(x,y) + self.get_caster_burst(x,y)

	def cast(self, x, y):
		for p in self.get_center_beam(x, y):
			self.caster.level.deal_damage(p.x, p.y, self.get_stat('damage'), Tags.Physical, self)
		for p in self.get_adj_beam(x, y):
			if p.x == self.caster.x and p.y == self.caster.y:
				continue
			self.caster.level.deal_damage(p.x, p.y, self.get_stat('damage'), Tags.Dark, self)
		for p in self.get_target_burst(x, y):
			if p.x == self.caster.x and p.y == self.caster.y:
				continue
			self.caster.level.deal_damage(p.x, p.y, self.get_stat('damage'), Tags.Poison, self)
		for p in self.get_caster_burst(x, y):
			if p.x == self.caster.x and p.y == self.caster.y:
				continue
			self.caster.level.deal_damage(p.x, p.y, self.get_stat('damage'), Tags.Holy, self)
		if self.quick_cast:
			self.caster.level.deal_damage(p.x, p.y, self.get_stat('damage'), Tags.Fire, self)
		if self.get_stat('num_targets') > 2:
			units = self.caster.level.get_units_in_ball(self.caster, self.get_stat('range'))
			hostiles = [u for u in units if are_hostile(self.caster, u)]
			if hostiles == []:
				return
			los_hostiles = [h for h in hostiles if self.caster.level.can_see(h.x, h.y, self.caster.x, self.caster.y)]
			random.shuffle(los_hostiles)
			targets = los_hostiles[:self.get_stat('num_targets')]
			for t in targets:
				for p in self.get_center_beam(t.x, t.y):
					self.caster.level.deal_damage(p.x, p.y, self.get_stat('damage') // 2, Tags.Lightning, self)
		yield



class TiamatAvatarGrowth(Buff):
	def __init__(self, spell):
		Buff.__init__(self)
		self.spell = spell
		self.color = Tags.Chaos.color
		self.name = "Consuming Wyrm"
		self.description = ("On kill, steal 10% of the targets max life, and 20% of damage from their spell's with damage.")
		self.buff_type = BUFF_TYPE_BLESS
		self.global_triggers[EventOnDeath] = self.on_death

	def on_death(self, evt):
		if not (evt.damage_event and evt.damage_event.source and evt.damage_event.source.owner == self.owner): ##TODO test for any events that might crash this
			return
		
		hp_bonus = evt.unit.max_hp // 10
		spell_dmg = 0
		for spell in evt.unit.spells:
			if not hasattr(spell, 'damage'):
				continue
			spell_dmg += spell.damage // 5
		buff = TiamatAvatarGrowStats(hp_bonus, spell_dmg)
		self.owner.apply_buff(buff, self.spell.get_stat('duration'))

class TiamatAvatarGrowStats(Buff):
	def __init__(self, hp, dmg):
		Buff.__init__(self)
		self.hp_bonus = hp
		self.dmg_bonus = dmg
		self.color = Tags.Chaos.color
		self.name = "Devoured"
		self.buff_type = BUFF_TYPE_BLESS
		self.stack_type = STACK_INTENSITY
		self.show_effect = False

	def on_applied(self, owner):
		life = self.hp_bonus
		self.owner.max_hp += life
		self.owner.cur_hp += life

		for spell in self.owner.spells:
			if not hasattr(spell, 'damage'):
				continue
			spell.damage += self.dmg_bonus
			
	def on_unapplied(self):
		life = self.hp_bonus
		self.owner.max_hp -= life
		if self.owner.cur_hp > self.owner.max_hp:
			self.owner.cur_hp = self.owner.max_hp
			
		for spell in self.owner.spells:
			if not hasattr(spell, 'damage'):
				continue
			spell.damage -= self.dmg_bonus

class TiamatBreath(BreathWeapon):
	def __init__(self):
		BreathWeapon.__init__(self)
		self.name = "Pyrostatic Breath"
		self.damage = 12
		self.damage_type = [Tags.Fire, Tags.Lightning]
		self.cool_down = 3
		self.range = 4
		self.angle = math.pi / 6.0

	def per_square_effect(self, x, y):
		unit = self.caster.level.get_unit_at(x, y)
		tag = random.choice(self.damage_type)
		if unit:
			self.caster.level.deal_damage(x, y, self.get_stat('damage'), tag, self)
		else:
			self.caster.level.show_effect(x, y, tag, minor=True)

class NidhoggsHunger(Buff):
	def __init__(self):
		Buff.__init__(self)
		self.buff_type = BUFF_TYPE_NONE
		self.show_effect = False
		
	def on_advance(self):
		for p in self.owner.level.get_adjacent_points(Point(self.owner.x, self.owner.y), filter_walkable=False):
			if self.owner.level.tiles[p.x][p.y].is_wall():
				self.owner.level.make_floor(p.x, p.y)
				self.owner.level.show_effect(p.x, p.y, Tags.Tongue)
				self.owner.max_hp += 13
				self.owner.cur_hp += 13

class EyeOfTiamat(ElementalEyeBuff):
	def __init__(self, damage, freq):
		ElementalEyeBuff.__init__(self, Tags.Physical, damage, freq) 
		self.name = "Eye of Typhon"
		self.color = Tags.Chaos.color
		self.asset = ['status', 'fire_eye'] ##TODO asset
		self.description = "Deals %d physical damage to a random enemy in LOS every %s turns" % (self.damage, freq)

class OuroBorosRevive(ReincarnationBuff):
	def __init__(self, lives=13):
		ReincarnationBuff.__init__(self)
		self.lives = lives
		self.owner_triggers[EventOnDeath] = self.on_death
		self.name = "Reincarnation %d" % self.lives
		self.buff_type = BUFF_TYPE_PASSIVE
		self.duration = 0
		self.turns_to_death = None
		self.shields = 0
		self.max_hp = 0

	def get_tooltip(self):
		return "Reincarnates when killed (%d times)" % self.lives

	def on_death(self, evt):
		if self.lives >= 1:
			to_remove = [b for b in self.owner.buffs if b.buff_type != BUFF_TYPE_PASSIVE and b.buff_type != BUFF_TYPE_ITEM]
			for b in to_remove:
				self.owner.remove_buff(b)

			self.lives -= 1
			self.old_pos = Point(self.owner.x, self.owner.y)
			self.owner.level.queue_spell(self.respawn())
			self.name = "Reincarnation %d" % self.lives
			wizard = self.owner.level.player_unit
			wizard.cur_hp -= 25
			self.owner.level.event_manager.raise_event(EventOnSpendHP(wizard, 25), wizard)

def ChaosWyrm():
	unit = Unit()
	unit.name = "Chaos Wyrm"
	unit.asset = ["TcrsCustomModpack", "Units", "chaos_wyrm"]
	unit.max_hp = 75

	unit.spells.append(TiamatBreath())
	unit.spells.append(SimpleMeleeAttack(12, trample=True))

	unit.tags = [Tags.Chaos, Tags.Dragon, Tags.Demon]
	unit.resists[Tags.Physical] = 75
	unit.resists[Tags.Lightning] = 75
	unit.resists[Tags.Fire] = 75
	unit.resists[Tags.Poison] = -100
	unit.resists[Tags.Arcane] = -100
	unit.resists[Tags.Heal] = 100
	return unit

class AvatarOfTiamat(Spell):
	def on_init(self):
		self.name = "Avatar of Tiamat"
		self.tags = [Tags.Chaos, Tags.Dragon, Tags.Conjuration]
		self.level = 7
		self.asset = ["TcrsCustomModpack", "Icons", "chaos_wyrm_icon"]
		
		self.max_charges = 1
		self.range = 3
		self.minion_health = 75
		self.minion_damage = 12
		self.minion_range = 3
		self.duration = 14

		self.must_target_empty = True
		self.must_target_walkable = True
			
		self.upgrades[('eye','shot_cooldown','damage')] = ([1,3,30], 6, "Eye of Typhon", "Every [3:shot_cooldown] turns, Avatars deal [30:damage] [physical] damage to a random enemy in their line of sight.", [Tags.Eye])
		self.upgrades['devour'] = (1, 1, "Hunger of Nidhogg", "Avatars gain burrowing. Each turn they consume all adjacent walls, gaining 13 max hp.")
		self.upgrades[('revival','hp_cost')] = ([1,25], 2, "Ouroboros", "Avatars gain 13 reincarnations, but you pay 25 hp every time an avatar dies.", [Tags.Blood])


	def get_description(self):
		return ("Summon an avatar of Tiamat.\nThe avatar has [{minion_health}_HP:minion_health] and a short [{minion_range}_tile:minion_range] breath weapon which deals [{minion_damage}:damage] [Fire] or [Lightning] damage, "
				"and a trampling melee attack which deals [{minion_damage}_physical:physical] damage."
				"\nAvatars consume stats from the enemies they kill, gaining 10% of their max health and 20% of their spell damage for [{duration}_turns:duration].\nThey are immune to healing.").format(**self.fmt_dict())
	
	def get_extra_examine_tooltips(self):
		return [self.wyrm(), self.spell_upgrades[0]]

	def wyrm(self):
		wyrm = ChaosWyrm()
		apply_minion_bonuses(self, wyrm)
		wyrm.buffs.append(TiamatAvatarGrowth(self))
		if self.get_stat('devour'):
			wyrm.buffs.append(NidhoggsHunger())
			wyrm.burrowing = True
		if self.get_stat('eye'):
			wyrm.buffs.append(EyeOfTiamat(self.get_stat('damage'),self.get_stat('shot_cooldown')))
		if self.get_stat('revival'):
			wyrm.buffs.append(OuroBorosRevive(13))
		return wyrm

	def cast_instant(self, x ,y):
		unit = self.wyrm()
		self.summon(unit, Point(x, y))




## Motion sickness, debuff an area (map?) deal damage on move and teleport
#monster.recolor_primary = Tags.Blood.color
# TODOD scroll convertor, rework preparation into a channel
## TODO Implement on another unit:
## self.upgrades['chrome'] = (1, 6, "Chromatic Abberation", "When the riftstalker kills a unit, if it has any tags that riftstalker does not already have, the riftstalker steals one tag and gains its max hp.") #TODO Move
## TODO Check random movement over chasms get_adjacent_point doesn't seem to work


def construct_spells():
	spellcon = [MetalShard, CorpseExplosion, FlyWheel, Rockfall, Improvise, Absorb, Haste, BloodOrbSpell, EnchantingCross, Icepath,
				SummonBookwyrm, Exsanguinate, Grotesquify, WordoftheSun, WordofFilth, HolyBeam, Amalgamate, SummonCauldron, OccultBlast,
				RingofFishmen, CallBerserker, ChaosBolt, Machination, Skulldiggery, SummonEyedra, ShieldOrb, PoisonousGas, Hemortar, 
				SummonIcyBeast, RainbowSeal, SteelFangs, Leapfrog, KnightlyLeap, SummonChaosBeast, BeckonCowardlyLion, PowerShift, Icebeam,
				TreeFormSpell, AnimateClutter, HP_X_Damage, Overload, UtterDestruction, DominoeAttack, UnstableSpellStorm, Cloudwalk, 
				TheSecondSeal, RainDemonMogui, MitreMovement, ChaosDice, WraithHunger, Landmines, SeaSerpent, 
				ChannelPylonSpell, SacrificialAltarSpell, RitualCircle, PrismaticSpray, OpalescentEyes, VileMenagerie,
				UnstableConcoction, AdvancingSandstorm, AstralProjection_TCRS, Telekinesis, TridentOfWoe, MirrorShield, Grist, RandomTeleport,
				TrueNameCurse, GalvanizedSummon, JekylPotion, SummonRiftstalker, IdolOfReflection, ObsidianDagger,
				WordofBlood, SlimePriestSpell, SummonCompassionAngel, OrbofBlindness, Verminform, RiftTremor, BloodTransfusion, FireEmUp,
				ChainBolt, SpiritOrb, SlimeRay, WolfChampion] ## CreepingFrost, Trebuchet, Dissolution, AstraVirtue, AdaptivePulse, AvatarOfTiamat ##Soon to be released, mostly finished
	
	print("Added " + str(len(spellcon)) + " spells")
	for s in spellcon:
		Spells.all_player_spell_constructors.append(s)