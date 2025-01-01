import sys
import os.path

from Variants import BagOfBugsBrain, BrainFlies
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
import copy


from mods.TcrsCustomModpack.SharedClasses import *

print("Custom Spells Loaded")

##TODO	Fix Flywheel's one missing pixel
##		Make the earliest icons like metal shard not use the old style icon which flashes between 7 frames
##		Use raise_elemental (CommonContent.py) to do something cool.

water_tag = Tag("Water", Color(14,14,250)) ##Purely for cross-mod compatibility

class Improvise(Spell):
	def on_init(self):
		self.name = "Improvise"
		self.asset = ["TcrsCustomModpack", "Icons", "improvise"]
		self.tags = [Tags.Chaos, Tags.Sorcery, Tags.Conjuration]
		self.level = 1
		
		self.max_charges = 21
		self.damage = 7
		self.range = 5
		self.minion_health = 7
		self.minion_duration = 7
		self.minion_damage = 3
		self.minion_range = 3

		self.upgrades['swarm'] = (1, 5, "Swarming", "If the target dies to Improvise, gain your imp swarm buff for 2 turns, or extend it by 2 turns.")
		self.upgrades['nightmare'] = (1, 3, "Nightmare", "Improvise also summons one void imp, or one rot imp, at the target location")
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
				#unit.turns_to_death = None ##Possibly last forever
				self.summon(unit=unit,target=point,team=self.caster.team)
				#print(time.time())
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
			spell = self.owner.get_or_make_spell(MetalShard)
			spell.echocast = True
			self.owner.level.act_cast(self.owner, spell, evt.x, evt.y, pay_costs=False)
			self.owner.remove_buffs(MetalShardEcho)

class MetalShard(Spell):

	def on_init(self):
		self.name = "Metal Shard"
		self.asset = ["TcrsCustomModpack", "Icons", "metal_shard"]
		self.tags = [Tags.Metallic, Tags.Sorcery]
		self.level = 1

		self.damage = 7
		self.range = 10
		self.damage_type = Tags.Physical
		self.max_charges = 18
		self.num_targets = 3
		self.echocast = False

		#Kinetic Cascade - Credit Mikhailo Kobiletski
		self.upgrades['echo'] = (1, 3, "Echoing Bounce", "When you cast metal shard, your next level 2 or higher spell also casts metal shard at the target.")
		self.upgrades['bouncer'] = (1, 2, "Anti-Inelastic Collision", "Each time Metal Shard ricochets, its damage increases by 100% of its base damage.")
		self.upgrades['UBW'] = (1, 3, "Unlimited Bounce Works", "Consume all charges to gain 1 bounce, 1 bounce range, and 1 damage per charge consumed.")
		#Name came before the upgrade, not a good sign

	def cast(self, x, y):
		#if self.caster.name == "Wizard":
		#	self.caster.xp = self.caster.xp + 3 ##Free xp for testing, comment out for real game.
		bolts = [(self.caster, Point(x, y))]
		ubw_bonus = 0
		if self.get_stat('UBW') and self.cur_charges > 1:
			ubw_bonus = self.cur_charges
			self.cur_charges = 0
		if self.get_stat('echo'):
			if not self.echocast:
				self.caster.apply_buff(MetalShardEcho())
			else:
				self.echocast = False

		target_count = self.get_stat('num_targets') + ubw_bonus
		bounce_range = math.ceil(self.get_stat('range')) / 2 + ubw_bonus
		damage = self.get_stat('damage') + ubw_bonus
		
		for _ in range(target_count): ##Weird bouncing behaviour, the code is straight from ricochet so it might also have this problem?
			prev_target = Point(x, y)
			candidates = [u for u in self.caster.level.get_units_in_los(Point(x, y))]
			candidates = [u for u in candidates if Point(u.x, u.y) != prev_target]
			candidates = [c for c in candidates if are_hostile(self.caster, c) and distance(c, prev_target) < bounce_range]
			if not candidates:
				break

			next_target = random.choice(candidates)
			bolts.append((prev_target, next_target))
			prev_target = next_target

		bouncer = 0
		for origin, target in bolts:
			#self.caster.level.projectile_effect(origin.x, origin.y, proj_name='physical_ball', proj_origin=origin, proj_dest=target)
			self.caster.level.show_beam(origin, target, Tags.Physical)
			self.caster.level.deal_damage(target.x, target.y, damage + bouncer, Tags.Physical, self)
			if self.get_stat('bouncer'):
				bouncer += int(self.get_stat('damage'))

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
	unit.asset = ["TcrsCustomModpack", "Units", "cauldron3"]
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
		self.upgrades['firevoid'] = (1, 5, "Potent Pot", "Adds gigantic variations of the fire and void toads. The cauldron gains 100 fire and arcane resistance.")
		self.upgrades['ghost'] = (1, 2, "Spooky Saucepan", "Add a towering variant of the ghost toad. The cauldron gains a dark damage aura for 2 damage in a 7 tile radius.")

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
		choices = [HornedToad(), FlameToad(), VoidToad(), GhostToad()]
		if self.get_stat('king'):
			choices[0] = HornedToadKing()
			choices.append(GiantToad())
		if self.get_stat('firevoid'):
			choices.append(FlameToadGiant())
			choices.append(VoidToadGiant())
		if self.get_stat('ghost'):
			choices.append(GiantToadGhost())
		return random.choice(choices)

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
		#self.asset = [] ##TODO make buff asset
		self.stack_type = STACK_DURATION
		self.owner_triggers[EventOnDeath] = self.on_death
		if self.spell.get_stat('remove_resistance'):
			self.resists[Tags.Fire] = -25
			self.resists[Tags.Physical] = -25
			
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
					unit.apply_buff(CorpseExplosionBuff(self.spell))
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

		self.range = 8
		self.max_charges = 12
		self.hp_cost = 4
		self.damage = 8
		self.radius = 4
		self.can_target_empty = False
		
		self.upgrades['remove_resistance'] = (1, 3, "Remove Resistances", "Target loses 25 physical and fire resistance.")
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
				"and spreads the debuff.\n").format(**self.fmt_dict())
	
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
		self.description = ("Whenever you cast a metallic spell, the number of summons of your next flywheel is increased by the level of the metallic spell.\n"
							"All minions summoned this way are metallic.\n")
		self.owner_triggers[EventOnSpellCast] = self.on_cast

	def on_cast(self, evt):
		if Tags.Metallic not in evt.spell.tags:
			return
		buff = AccumulatorBuff(self)
		buff.level = evt.spell.level
		buff.description = "Summon " + str(buff.level) + " extra bags of bugs, and turn them metallic"
		self.owner.apply_buff(buff)

class FlyWheel(Spell):

	def on_init(self):
		self.name = "Flywheel"
		self.asset = ["TcrsCustomModpack", "Icons", "flywheel"]
		self.level = 2 ##Aiming for level 2, scales well with skills, but starts weak.
		self.tags = [Tags.Nature, Tags.Conjuration]
		
		self.range = 0
		self.max_charges = 5
		self.minion_health = 16
		self.minion_damage = 4
		self.minion_duration = 5
		self.radius = 3
		self.num_summons = 2
		
		self.add_upgrade(Accumulator())
		self.upgrades['arcane'] = (1, 2, "Arcanization", "Summons brain bugs and brain flies, and melts walls in the ring.")
		self.upgrades['bigbag'] = (1, 4, "Giant Bag", "Replace the bags of bugs with giant bags of bugs.")

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
			if unit is None and self.caster.level.tiles[point.x][point.y].can_see:
				if flybags > 0:
					flybags -= 1
					if self.get_stat('arcane'):
						unit = BagOfBugsBrain()
					elif self.get_stat('bigbag'):
						unit = BagOfBugsGiant()
					else:
						unit = BagOfBugs()
					apply_minion_bonuses(self, unit)
					unit.turns_to_death = None

				else:
					if self.get_stat('arcane'):
						unit = BrainFlies()
					else:
						unit = FlyCloud()

					unit.max_hp = self.get_stat('minion_health') // 4
					unit.damage = self.get_stat('minion_damage') // 4
					apply_minion_bonuses(self, unit)


				if bonus_summons > 0:
					BossSpawns.apply_modifier(BossSpawns.Metallic, unit)
				self.summon(unit, point)
				
	def get_impacted_tiles(self, x, y):
		points = self.caster.level.get_points_in_ball(self.caster.x, self.caster.y, self.get_stat('radius'))
		points = [p for p in points if p != Point(self.caster.x, self.caster.y) and distance(self.caster, p) >= self.radius - 1]
		return points

	def get_extra_examine_tooltips(self): ##TODO fix the flycloud and giant bag of bugs
		return [BagOfBugs(), FlyCloud(), self.spell_upgrades[0], BagOfBugsBrain(), BrainFlies(), self.spell_upgrades[1], BagOfBugsGiant(), self.spell_upgrades[2]]

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
		
		self.range = 7
		self.max_charges = 15
		self.damage = 30
		self.radius = 1
		self.mod_radius = 3
		self.cast_on_walls = True

		#self.upgrades['rolling'] = (1, 0, "Rolling Stone", "Deal damage in a wide line towards the target instead of just at the area.")
		self.upgrades['radius'] = (2, 3, "Radius")
		self.upgrades['earthquake'] =  (1, 4, 'Quaker', 'Cast earthquake at your location after this spell.')
		self.upgrades['walleater'] = (1, 3, 'Walleater', 'If the center tile is a wall, cast earth sentinel at that point.')
		self.upgrades['chaos'] = (1, 5, 'Chaotic Rock', 'Also deal fire or lightning damage to each tile.')

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
		if cur_tile.is_wall() and self.get_stat('walleater'): ##TODO buff this to include any wall tile in the aoe not just the center? Is it too weak?
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
		
		self.range = 1
		self.melee = True ##Revert if I can figure out this stupid spell.
		self.cast_on_walls = True
		self.can_target_self = False
		self.damage = 45
		self.max_charges = 6
		self.total_damage = 0

		self.upgrades['knight'] = (1, 4, "Storm Beam", "Each 180 damage dealt by the beam summons a storm knight.")
		self.upgrades['icemaw'] = (1, 4, "Icy Maw", "Cast your hungry maw on tiles where an enemy died to this spell.")
		self.upgrades['chasm'] = (1, 3, "Faery", "Summons winter faeries over each chasm. They last 11 turns.")
		##self.upgrades['backwards'] = (1, 3, "Backblast", "Deal fire damage in a cone behind you after casting.")
			
	def get_description(self):
		return ("Deals [{damage}_ice:ice] damage in a straight beam. The beam pierces walls and continues until the end of the level.\n"
			   "Debuff yourself for 3 turns or until you cast a [fire] spell. If you cast another [ice] spell with the debuff, freeze for 3 turns.").format(**self.fmt_dict())

	def get_extra_examine_tooltips(self): 
		return [self.spell_upgrades[0], StormKnight(), self.spell_upgrades[1], self.spell_upgrades[2], FairyIce()]

	def cast(self,x,y):
		if self.caster.has_buff(IcebeamDebuff):
			self.caster.apply_buff(FrozenBuff(),3)
		else:
			self.caster.apply_buff(IcebeamDebuff(self),3)
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

	def get_impacted_tiles(self, x, y):
		size = copy.copy(self.caster.level.width) #Probably needlessly careful about object references
		size_y = copy.copy(self.caster.level.height)
		start = Point(self.caster.x, self.caster.y)
		run = self.caster.x - x
		rise = self.caster.y - y
		if run == 0 and rise == 0:
			return
		finalx = x
		finaly = y
		while finalx >= 0 and finalx <= size and finaly >= 0 and finaly <= size: ##TODO Ensure this works on the edge of the map
			finalx -= run
			finaly -= rise

		if finalx > size: ##Problem has something to do with the final calculation on the edges. Notably different at the top left from bottom right.
			finalx = size ##I think there's a problem here when you start one single tile away from the edge.

		if finaly > size:
			finaly = size

		if finalx < 0:
			finalx = 0

		if finaly < 0:
		 	finaly = 0

		target = Point(finalx,finaly)

		#print('ice beam debug')
		#print(str(self.caster.x) + ":" + str(self.caster.y) + " - " + str(finalx) + ":" + str(finaly))
		#points = self.caster.level.get_points_in_line(self.caster, target)
		#for p in Bolt(self.caster.level, start, target, find_clear=False):
		#	if self.caster.level.is_point_in_bounds(p):
		#		points.append(p)
		#return points
		return list(Bolt(self.caster.level, start, target, find_clear=False, two_pass=False))


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
		
		self.range = 1
		self.max_charges = 5
		self.melee = True
		self.can_target_empty = False
		self.damage = 50
		self.duration = 20
		self.bonus = 10

		self.upgrades['bonus'] = (5, 2, "Damage Bonus")
		self.upgrades['minionbonus'] = (1, 2, "Minion Damage", "Applies damage bonus to minion damage as well.")
		self.upgrades['stealresist'] = (1, 4, "Barrier", "Copy the target's resistances as well.")
		self.upgrades['quick_cast'] = (1, 3, "Quickcast", "Casting absorb does not end your turn, deals 90% less damage.")

	def get_description(self):
		return ("Deal [{damage}_arcane:arcane] damage to one unit in melee range, then gain {bonus} bonus damage to spells based on the target's tags.\n"
				"Convert all damage tags e.g. [Fire] enemies to [Fire] spell damage, and also converts [Living] to [Nature], [Undead] to [Dark] damage.\n"
				"Lasts 20 turns. Does not stack.").format(**self.fmt_dict())

	def cast_instant(self, x, y):
		unit = self.caster.level.get_unit_at(x, y)

		buff = AbsorbBuff(self)
		tagconv = TagConvertor()
		for t in unit.tags:
			if t in tagconv:
				t = copy.deepcopy(tagconv[t])
			buff.tag_bonuses[t]['damage'] = self.bonus
			if self.get_stat('minionbonus'):
				buff.tag_bonuses[t]['minion_damage'] = self.bonus
				
		if self.get_stat('stealresist'):
			res_vals = []
			for tag in unit.resists.keys():
				if tag != Tags.Heal:
					resval = unit.resists[tag]
					res_vals.append([tag,resval])
			defense_buff = BarrierBuff(res_vals,self.get_stat('duration'))
			self.caster.apply_buff(defense_buff)

		damage = self.get_stat('damage')
		if self.get_stat('quick_cast'):
			damage = damage * 0.10
		unit.deal_damage(damage, Tags.Arcane, self)
		self.caster.apply_buff(buff, self.get_stat('duration'))
		
	

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
		self.tags = [Tags.Lightning, Tags.Enchantment]
		self.level = 2 #Hard to judge its efficiency, this spell scales with your minions.
		self.asset = ["TcrsCustomModpack", "Icons", "haste_icon"]
		
		self.max_charges = 15
		self.max_channel = 15
		self.requires_los = False
		self.can_target_empty = False
		self.can_target_self = False
		self.range = 99
		self.num_targets = 2
		
		self.upgrades['num_targets'] = (4, 3, "Multi Haste", "Increases the amount of allies which can be affected by 4.")
		self.add_upgrade(HasteUpgrade())
		self.upgrades['enduring'] = (1, 1, "Endurance", "No longer channeled, instead lasts for [10:duration] turns. Does not re-cast itself each turn.")

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
					#print(u.name)
					count -= 1
					buff = HasteBuff()
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
		self.level = 4 ##Immediately comparable to cantrip cascade, but worse. Level 4? It's actually pretty reasonable. Level 5?
		self.tags = [Tags.Arcane, Tags.Enchantment]
		self.asset = ["TcrsCustomModpack", "Icons", "enchanting_cross"]
		self.max_charges = 3
		self.range = 0
		self.radius = 8
		self.requires_los = False
		
		#self.upgrades[''] = (1, 1, "", "")
		self.upgrades['selfbuff'] = (1, 4, "Selfish", "Casts one of your self targeted enchantments randomly for free.")
		self.upgrades['doublecross'] = (1, 3, "Double Cross", "Adds a diagonal cross.")

	def get_description(self):
		return ("Cast one of your level 3 or lower [enchantment] spells on each enemy in a [{radius}_tile:radius] cross for free.\n"
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
		spells = [s for s in self.caster.spells if Tags.Enchantment in s.tags and not s.name == "Enchanting Cross"]
		targ_spells = []
		self_spells = []
		for s in spells:
			if s.range == 0:
				self_spells.append(s)
			elif s.level <= 3:
				targ_spells.append(s)
				
		if self.get_stat('selfbuff'):
			if self_spells == []:
				return
			#print(self_spells[0].name)
			self_spell = random.choice(self_spells)
			self.caster.level.act_cast(self.caster, self_spell, self.caster.x, self.caster.y, pay_costs=False)
			
		units = [self.caster.level.get_unit_at(p.x, p.y) for p in self.get_impacted_tiles(x, y)]
		enemies = set([u for u in units if u and are_hostile(u, self.caster)])
		pairs = list(itertools.product(enemies, targ_spells))
		#print(pairs)
		random.shuffle(pairs)
		
		if spells == None or units == None:
			return
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
		self.range = 9
		self.max_charges = 4
		self.minion_health = 30
	
		self.upgrades['range'] = (5, 3, "Range", "Gains 5 max range.")
		self.upgrades['worm'] = (1, 5, "Lumbricus", "When the orb dies it creates a wormball with max hp equal to the damage the orb dealt to enemies.")
		self.upgrades['deathshock'] = (1, 6, "Bloody Shocking", "You casts your death shock on a random enemy for each 50 damage the orb deals to enemies.")

	def on_orb_move(self, orb, next_point):
		for _ in self.caster.level.act_cast(orb, orb.spells[0], orb.x, orb.y, pay_costs=False, queue=False):
			pass
		orb.spells[0].radius += 1

	def on_make_orb(self, orb):
		orb.name = "Blood Orb"
		orb.asset =  ["TcrsCustomModpack", "Units", "blood_orb"]
		orb.tags.append(Tags.Blood)
		orb.resists[Tags.Physical] = 0
		orb.max_hp = self.minion_health * 5 ##This is not important anymore.
		orb.cur_hp = self.minion_health
		grant_minion_spell(Spells.DrainPulse, orb, self.caster)
		orb.spells[0].radius = 1
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
		self.description = ("Target a point to create a path for your wizard to automatically move towards, one tile per turn. Can cross chasms, cannot displace units.\n"
							"Become immune to [ice] during the effect. Target another tile to change your destination.\n"
							"Casting this spell doesn't end your turn. The buff ends if you teleport.").format(**self.fmt_dict())
		self.range = 10
		self.max_charges = 15
		self.quick_cast = 1
		self.must_target_empty = True
		
		self.upgrades['storms'] = (1, 2, "Cloak of Storms", "Deal 8 [Ice] and 8 [Lightning] damage to 1 unit in line of sight each turn.")
		self.upgrades['reaper'] = (1, 1, "Reaper's Path", "If there is a unit blocking your path, use your touch of death on it before attempting to move.")
		self.upgrades['thorn'] = (1, 4, "Thornpath", "Summon icy thorns each turn in the tile behind you.")

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
		self.damage = 7
		self.damage_types = [Tags.Fire, Tags.Ice, Tags.Lightning, Tags.Arcane, Tags.Dark, Tags.Poison, Tags.Holy, Tags.Physical]
		self.cool_down = 6
		self.scrolls = ScrollConvertor()
		self.scrolls[Tags.Metallic] = MetalShard,LivingMetalScroll()

	def get_description(self):
		return "Breathes a cone of pure linguistics dealing %d damage to occupied tiles and summoning scrolls in empty ones." % self.damage

	def make_scrolls(self,tag):
		if tag == Tags.Poison:
			tag = Tags.Nature
		elif tag == Tags.Physical:
			tag = Tags.Metallic
		unit = copy.deepcopy(self.scrolls.get(tag)[1])
		grant_minion_spell(copy.deepcopy(self.scrolls.get(tag)[0]), unit, self.caster, 3)
		unit.apply_buff(LivingScrollSuicide())
		return unit

	def per_square_effect(self, x, y):
		tag = random.choice(self.damage_types)
		scroll = self.make_scrolls(tag)
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
		self.range = 0
		self.max_charges = 1
		self.tags = [Tags.Word, Tags.Dragon, Tags.Conjuration]
		self.asset = ["TcrsCustomModpack", "Icons", "word_of_wyrms"]
		self.level = 7
		
		example = BookWyrm()
		self.minion_health = example.max_hp
		self.breath_damage = example.spells[0].damage
		self.minion_range = example.spells[0].range
		self.minion_damage = example.spells[1].damage
		self.duration = 1		

		#self.upgrades['echo'] = (1, 5, "Echoing Roar", "Auto recasts in 10 turns.")
		self.upgrades['duration'] = (1, 1, "Terrifying", "The fear lasts for 1 more turn.")
		self.upgrades['vigor'] = (1, 1, "Vigor", "Heal all dragons to full health.")

	def get_description(self):
		return ("Fears all non [Dragon] units for 1 turn, then Summon a Bookwyrm at your location. The Bookwyrm is a dragon whose breath deals:\n" 
				"[Fire], [Lightning], [Ice], [Arcane], [Holy], [Dark], [Poison], or [Physical] damage, while summoning scrolls that cast cantrips in empty squares.").format(**self.fmt_dict())

	def get_extra_examine_tooltips(self):
		return [BookWyrm(), self.spell_upgrades[0], self.spell_upgrades[1]]

	def cast_instant(self, x, y):
		units = [u for u in self.caster.level.units if Tags.Dragon not in u.tags and not u.is_player_controlled]
		for unit in units:
			unit.apply_buff(FearBuff(), self.get_stat('duration'))
		if self.get_stat('vigor'):
			units = [u for u in self.caster.level.units if Tags.Dragon in u.tags]
			for unit in units:
				unit.deal_damage(-unit.max_hp, Tags.Heal, self)
		unit = BookWyrm()
		apply_minion_bonuses(self, unit)
		self.summon(unit, Point(x, y))

	
def BloodSlime():

	unit = Unit()

	unit.name = "Blood Slime"
	unit.asset = ["TcrsCustomModpack", "Units", "blood_slime"] ##TODO Figure out if this sprite caused a crash. Hasn't had any problems since.
	unit.max_hp = 10

	unit.tags = [Tags.Slime, Tags.Blood]

	unit.spells.append(SimpleRangedAttack(damage=3, damage_type=Tags.Dark, range=3))
	unit.buffs.append(SlimeBuff(spawner=BloodSlime))

	unit.resists[Tags.Dark] = 50
	unit.resists[Tags.Physical] = 25
	unit.resists[Tags.Holy] = -25

	return unit

class Exsanguinate(Spell):
	
	def on_init(self):
		self.name = "Exsanguinate"
		self.tags = [Tags.Blood, Tags.Conjuration, Tags.Sorcery]
		self.asset = ["TcrsCustomModpack", "Icons", "exsanguinate"]
		self.level = 4 ##Considering level 4 and giving it a large charge reserve with a medium health cost. Maybe level 5 and buffing its range and damage?
		self.hp_cost = 10 #High hp cost and high charges?
		
		self.max_charges = 9
		self.range = 4
		self.can_target_empty = False
		self.damage = 20
		self.damage_types = [Tags.Dark, Tags.Poison]
		self.sum_dmg = {Tags.Dark:0,Tags.Poison:0,Tags.Arcane:0, Tags.Fire:0, Tags.Ice:0}
		
		self.magus = 0
		self.example = BloodWizard()
		self.example.max_hp = 100
		self.slimes = {Tags.Poison:GreenSlime(), Tags.Dark:BloodSlime(), Tags.Arcane:VoidSlime(), Tags.Fire:RedSlime(), Tags.Ice:IceSlime()}
		self.minion_health = 10
		self.minion_damage = 3

		self.upgrades['frostfire'] = (1, 5, "Frostfire", "Adds [Fire] and [Ice] damage, and Red Slimes and Ice Slimes.")
		self.upgrades['nightmare'] = (1, 2, "Nightmare", "Adds arcane damage and void slimes.")
		self.upgrades['wizard'] = (1, 4, "Blood Magic", "For every 100 damage dealt by the spell directly, summon a blood magus.")
		#self.upgrades['slimeform'] = (1, 0, "Slime Coating", "When you cast the first or last charge of this spell, cast your slime form as well.") ##TODO implement

	def cast_instant(self, x, y):
		damage_types = copy.copy(self.damage_types)
		if self.get_stat('frostfire'):
			damage_types.append(Tags.Fire)
			damage_types.append(Tags.Ice)
		if self.get_stat('nightmare'):
			damage_types.append(Tags.Arcane)
		
		random.shuffle(damage_types)
		unit = self.caster.level.get_unit_at(x, y)
		for tag in damage_types:
			temp_damage = unit.deal_damage(self.get_stat('damage'), tag, self)
			self.sum_dmg[tag] += temp_damage
			if self.get_stat('wizard'):
				self.magus += temp_damage
		for tag in self.sum_dmg:
			while self.sum_dmg[tag] > 10:
				slime = copy.deepcopy(self.slimes[tag])
				apply_minion_bonuses(self, slime)
				self.summon(slime, Point(x,y), radius = 3,sort_dist=True)
				self.sum_dmg[tag] = self.sum_dmg[tag] - 10
				
		if self.get_stat('wizard'):
			while self.magus >= 100:
				u = BloodWizard()
				u.max_hp = 100
				apply_minion_bonuses(self,u)
				self.summon(u)
				self.magus -= 100

	def get_extra_examine_tooltips(self):
		return [BloodSlime(), GreenSlime(), self.spell_upgrades[0], RedSlime(), IceSlime(), self.spell_upgrades[1], VoidSlime(), self.spell_upgrades[2], self.example]

	def get_description(self):
		return ("Deal [{damage}_poison:poison] damage and [{damage}_dark:dark] to one unit, " +
				"then summon a green slime or blood slime for each 10 damage dealt for each damage type.\n"
				"Slimes have [{minion_health}_HP:minion_health] and deal {minion_damage} damage.").format(**self.fmt_dict())

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
		self.level = 2 ##Adding allied interactions to make this more interesting
		self.asset = ["TcrsCustomModpack", "Icons", "slow_petrify"]
		
		self.max_charges = 15
		self.range = 8
		self.can_target_empty = False
		
		self.upgrades['gargoyle'] = (1, 3, "Grotesquery", "Enemies now also become a Gargoyle, or if it had more than 100 max hp, a Mega Gargoyle")
		self.upgrades['group'] = (1, 5, "Connection", "Curses a group of connected enemies.")
		self.upgrades['eyes'] = (1, 2, "Watching Ornaments", "The Crumbling Statue casts Eye of Fire, Lightning, or Ice randomly.") ##Kinda bizarre, but weird eye synergies fun

	def get_description(self):
		return ("Curses a unit to slowly petrify, granting the target 50% resistance to [Physical], [Fire], [Ice], and [Lightning] damage. "
				"When the curse ends, transform the unit into a statue.\n"
				"Allied minions turn into Gargoyles and enemies into Crumbling Statues.\n"
				"The curse lasts for 1 turn for each 10 max hp the target has.\n"
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
			if duration > 0:
				unit.apply_buff(GrotesqueBuff(self),duration)
			else:
				self.make_gargoyle(t.x, t.y)

	def make_gargoyle(self, x, y):
		p = Point(x, y)
		u = self.owner.level.get_unit_at(x, y)

		if self.get_stat('gargoyle') or not are_hostile(u, self.owner):
			if u.max_hp < 100:
				unit = Gargoyle()
			else:
				unit = MegaGargoyle()
		else:
			unit = GrotesqueStatue()
			unit.turns_to_death = 10
			if self.get_stat('eyes'):
				spell = random.choice([EyeOfFireSpell,EyeOfIceSpell,EyeOfLightningSpell])
				grant_minion_spell(spell, unit, self.owner, cool_down=5)
		unit.team = self.owner.team
		apply_minion_bonuses(self, unit)
		u.kill()
		self.owner.level.summon(self.owner, unit, p, team=unit.team)

	def get_impacted_tiles(self, x, y):
		tiles = [Point(x, y)]
		if self.get_stat('group'):
			tiles = self.caster.level.get_connected_group_from_point(x, y, check_hostile=self.caster)
		return tiles

def Tachi():
	unit = DancingBlade()
	unit.name = "Tachi"
	unit.asset = ["TcrsCustomModpack", "Units", "spectral_blade_amaterasu4"]
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
		self.tags = [Tags.Fire, Tags.Holy, Tags.Word]
		self.asset = ["TcrsCustomModpack", "Icons", "word_of_the_sun"]
		self.level = 7
		self.range = 0
		self.damage = 25
		self.duration = 10
		self.max_charges = 1

		self.upgrades['aztec'] = (1, 2, "Tonatiuh", "Explodes all of your allies, dealing their current hp as fire damage in a 4 tile burst.")
		self.upgrades['egyptian'] = (1, 4, "Ra-Horakhty", "Summons an avian wizard and a raven mage.")
		self.upgrades['japanese'] = (1, 4, "Amaterasu", "Summons a powerful dancing blade which can leap and attack two times per turn.")

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
		
		self.range = 0
		self.max_charges = 1
		self.minion_health = 25
		self.minion_duration = 7
		self.minion_damage = 7
	
		self.upgrades['permanent'] = (1, 5, "Endurance", "Half of the units summoned are permanent units.")
		self.upgrades['toxic'] = (1, 3, "Toxicity", "Poisons every unit on the map for 3 turns.")
		self.upgrades['undeath'] = (1, 2, "Undeath", "Applies your plague of undeath debuff to every enemy unit.")

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
					u.apply_buff(RotBuff(hallowflesh))
		tiles = self.caster.level.iter_tiles()
		for t in tiles:
			if random.random() > 0.90:
				u = None
				if self.caster.level.tiles[t.x][t.y].is_chasm:
					u = FlyCloud()
					u.max_hp = self.get_stat('minion_health') / 4
					u.spells[0].damage = self.get_stat('minion_damage') / 3
				elif self.caster.level.tiles[t.x][t.y].is_wall():
					self.caster.level.make_floor(t.x, t.y)
					u = RockWurm()
					u.max_hp = self.get_stat('minion_health')
					u.spells[0].damage = self.get_stat('minion_damage')
				elif self.caster.level.tiles[t.x][t.y].is_floor():
					u = MindMaggot()
					u.max_hp = self.get_stat('minion_health') / 2
					u.spells[0].damage = self.get_stat('minion_damage') / 2
				else:
					u = GoatHead() ##TODO this was reached once and it confused me.

				if u != None:
					duration = random.randint(1, self.get_stat('minion_duration'))
					if self.get_stat('permanent'):
						if random.random() > 0.50:
							u.turns_to_death = duration
					else:
						u.turns_to_death = duration
					self.summon(u,target=Point(t.x,t.y))
			yield
			
	def get_description(self):
		return ("All empty tiles on the map have a 10% chance to spawn a unit.\n"
				"Each chasm can spawn a fly cloud, each wall can spawn a rockworm, and each floor can spawn a mind maggot.\n"
				"The units last for a random number of turns between 2 and [{minion_duration}_turns:minion_duration].").format(**self.fmt_dict())
	
class HolyBeamBattery(Buff):
	def __init__(self, spell):
		self.damage = spell.cur_damage // 2
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
		self.range = 16
		self.max_charges = 6

		self.damage = 80
		self.cur_damage = self.damage
		self.requires_los = False

		self.upgrades['healing'] = (1, 1, "Healing Inversion", "Your beam now heals allies instead of damaging them. It loses no damage from this.")
		self.upgrades['battery'] = (1, 4, "Battery", "If your beam has more than 5 damage remaining, add half its damage to the next beam.")
		self.upgrades['wallsucker'] = (1, 2, "Walleater", "Walls are now destroyed to add 20 damage to the beam.")

	def cast(self, x, y):
		self.cur_damage = self.get_stat('damage')
		for point in self.get_impacted_tiles(x,y):
			#print(point)
			if self.caster.level.tiles[point.x][point.y].is_wall():
				if self.get_stat('wallsucker'):
					self.caster.level.make_floor(point.x, point.y)
					self.cur_damage += 20
				else:
					self.cur_damage -= 20

			if self.get_stat('healing'):
				unit = self.caster.level.get_unit_at(point.x, point.y)
				if self.caster.level.are_hostile(self.caster, unit):
					self.cur_damage -= self.caster.level.deal_damage(point.x, point.y, self.get_stat('cur_damage'), Tags.Holy, self)
				else:
					self.caster.level.deal_damage(point.x, point.y, -self.get_stat('cur_damage'), Tags.Healing, self)
			else:
				self.cur_damage -= self.caster.level.deal_damage(point.x, point.y, self.get_stat('cur_damage'), Tags.Holy, self)
				
			if self.cur_damage <= 5:
				self.cur_damage = 5
			elif self.get_stat('battery'):
				self.caster.apply_buff(HolyBeamBattery(self))
		yield

	def get_impacted_tiles(self, x, y):
		start = Point(self.caster.x, self.caster.y)
		target = Point(x, y)
		points = []
		path = Bolt(self.caster.level, start, target, two_pass=False, find_clear=False)
		for point in path:
			points.append(point)
		return points

	def get_description(self):
		return ("Deal [{damage}_holy:holy] damage to units in a beam. Pierces but does not destroy walls.\n"
				"The beam loses damage equal to the damage it dealt to any units, and loses 20 damage on each wall."
				"The minimum damage of the beam is 5.").format(**self.fmt_dict())
				

class MirrorShieldBuff(Buff):
	def __init__(self, spell):
		self.spell = spell
		Buff.__init__(self)

	def on_init(self):
		self.buff_type = BUFF_TYPE_BLESS
		self.name = "Mirror Shield"
		self.color = Tags.Arcane.color
		#self.owner_triggers[EventOnSpellCast] = self.on_cast
		self.global_triggers[EventOnSpellCast] = self.on_cast
		self.stack_type = STACK_REPLACE
		#self.spell.can_target_self = False
		self.mirror = None
		self.description = "Cast the last spell cast on you."
		
	def on_cast(self, evt):
		wiz_p = Point(self.owner.x,self.owner.y)
		target_p = Point(evt.x,evt.y)
		if wiz_p == target_p:
			print("Target of spell")
			print(evt.spell.name)
			self.mirror = evt.spell
			self.description = "Cast the last spell cast on you: " + evt.spell.owner.name + "'s " + evt.spell.name

class MirrorShield(Spell):
	def on_init(self):
		self.name = "Mirror Shield"
		self.tags = [Tags.Arcane,Tags.Enchantment,Tags.Metallic, Tags.Sorcery]
		#self.asset = ["TcrsCustomModpack", "Icons", "holy_beam"]
		self.description = "Buff yourself, granting 1 shield and changing the behaviour of this spell. It gains cast range and its next cast mimics the last attack used on you."
		self.level = 1
		self.range = 5
		self.can_target_self = True
		self.max_charges = 40
		##So enormously difficult to balance that I'm tempted to limit it to SimpleMelee and SimpleRanged attacks and then have it trigger automatically.
		##Good idea me, TODO implement a new transformation buff asset (wizard with a shield-staff) and then make it automatically reflect.
		
	def cast(self, x, y):
		if not self.caster.has_buff(MirrorShieldBuff):
			self.caster.apply_buff(MirrorShieldBuff(self))
		else:
			buff = self.caster.get_buff(MirrorShieldBuff)
			if buff.mirror == None:
				return
			spell = copy.deepcopy(buff.mirror)
			#self.caster.spells.append(spell)
			spell.owner = self.caster
			spell.caster = self.caster
			spell.statholder = self.caster
			#for f in dir(spell):
			#	print(f)
			#self.caster.spells.append(spell)
			self.caster.level.act_cast(self.caster, spell, x, y, pay_costs=False)
			buff.mirror = None
			yield

	#def get_impacted_tiles(self, x, y):
	#	point = [self.owner.level.tiles[x][y]]
	#	return point
	
	def get_targetable_tiles(self):
		if not self.caster.has_buff(MirrorShieldBuff): return [Point(self.caster.x,self.caster.y)]
		candidates = self.caster.level.get_points_in_ball(self.caster.x, self.caster.y, self.get_stat('range'))
		return [p for p in candidates if self.can_cast(p.x, p.y)]

def AmalgamateUnit():
	unit = Unit()
	unit.name = "Amalgamation"
	unit.max_hp = 1
	unit.asset =  ["TcrsCustomModpack", "Units", "amalgamate_med"] #Credit to K.Hoops for the flesh fiend sprite. Its mouth serves as the basis for all amalgams.
	unit.buffs.append(RegenBuff(5))
	unit.tags = [Tags.Living, Tags.Construct]

	unit.resists[Tags.Physical] = -50
	unit.resists[Tags.Poison] = -50

	return unit

class Amalgamate(Spell): ##TODO there's something wrong with this spell. I think its doing some copy shenaningans.
	def on_init(self):
		self.name = "Amalgamation"
		self.tags = [Tags.Dark, Tags.Conjuration, Tags.Enchantment]
		self.asset =  ["TcrsCustomModpack", "Icons", "amalgamate_icon"]
		self.level = 5 ##Level 4? 5? Comparisons are mass calcification (converts max hp of all units into bone shambers, so similar to amalgamating your whole army)
		##Produces extremely powerful units but they can only take 1 action per turn, would likely decrease overall DPS
		self.can_target_empty = False
		self.max_charges = 5
		self.range = 10
		self.viable_tags = [Tags.Living, Tags.Nature]
		
		self.upgrades['elemental'] = (1, 2, "Elemental", "Adds Fire, Lightning, Ice as viable tags.")
		self.upgrades['ethereal'] = (1, 2, "Ethereal", "Adds Arcane, Holy, Dark, and Demon as viable tags. Gains 3 shields.")
		self.upgrades['creature'] = (1, 3, "The Creature", "Adds Metallic, Construct, Glass, and Undead as viable tags. Becomes immune to physical, poison.")
		#self.upgrades['strange'] = (1, 0, "Strange", "Adds Dragon, Chaos, Slime, whatever as viable tags. Can learn breath attacks.")

	def get_description(self):
		return ("Amalgamates a connected group of allied [Living], or [Nature] units, killing them and spawning an Amalgamation at the target location.\n"
				"The Amalgamation has the combined max hp of all units, their tags, regens 5 hp per turn, and combines their simple spells. "
				"Simple spells are melee attacks, leaps, and most ranged attacks.").format(**self.fmt_dict())

	def get_impacted_tiles(self, x, y):
		candidates = set([Point(x, y)])
		unit_group = set()
		if self.get_stat('elemental'):
			tags = [Tags.Fire, Tags.Ice, Tags.Lightning]
			for t in tags:
				self.viable_tags.append(t)
		if self.get_stat('ethereal'):
			tags = [Tags.Arcane, Tags.Holy, Tags.Dark, Tags.Demon]
			for t in tags:
				self.viable_tags.append(t)
		if self.get_stat('creature'):
			tags = [Tags.Metallic, Tags.Construct, Tags.Glass, Tags.Undead]
			for t in tags:
				self.viable_tags.append(t)
		while candidates:
			candidate = candidates.pop()
			unit = self.caster.level.get_unit_at(candidate.x, candidate.y)
			if unit and unit not in unit_group:
				if self.caster.level.are_hostile(self.caster, unit):
					continue
				
				viable = False
				for tag in unit.tags:
					if tag in self.viable_tags:
						viable = True
				if not viable:
					continue

				unit_group.add(unit)

				for p in self.caster.level.get_adjacent_points(Point(unit.x, unit.y), filter_walkable=False):
					candidates.add(p)

		return list(unit_group)

	def cast_instant(self, x, y):
		points = self.get_impacted_tiles(x, y)
		amalg = AmalgamateUnit()
		amalg_spells = {}
		for p in points:
			unit = self.caster.level.get_unit_at(p.x, p.y)
			if unit == self.caster: continue
			viable = False
			if unit:
				#print(unit.name)
				for tag in unit.tags:
					if tag in self.viable_tags:
						viable = True
				if viable:
					for tag in unit.tags:
						if tag not in amalg.tags:
							amalg.tags.append(tag)
					amalg.max_hp += unit.max_hp
					for s in unit.spells:
						if not isinstance(s, (SimpleMeleeAttack, SimpleRangedAttack, LeapAttack)):
							continue
						if s.name in amalg_spells: ##Reconsider if this should combine spells because it's probably causing huge problems lol.
							amalg_spells[s.name].damage += s.damage
						else:
							amalg_spells[s.name] = copy.deepcopy(s)
					self.caster.level.show_effect(unit.x, unit.y, Tags.Dark, minor=False)
					unit.kill()
		if amalg.max_hp == 1:
			return
		elif amalg.max_hp <= 24:
			amalg.asset = ["TcrsCustomModpack", "Units", "amalgamate_small"]
		elif amalg.max_hp <= 120:
			amalg.asset = ["TcrsCustomModpack", "Units", "amalgamate_med"]
		else:
			amalg.asset = ["TcrsCustomModpack", "Units", "amalgamate_large"]
		for k in amalg_spells:
			amalg.spells.append(amalg_spells[k])
			
		if self.caster.level.tiles[p.x][p.y].is_chasm:
			amalg.flying = True
		if self.get_stat('elemental'):
			pass ##Any buffs needed or are these just useful tags?
		elif self.get_stat('etheral'):
			amalg.shields = 3
		elif self.get_stat('automaton'):
			amalg.resists[Tags.Physical] = 100
			amalg.resists[Tags.Poison] = 100

			
		self.caster.level.summon(self.caster, amalg, Point(x,y))

class OccultBlast(Spell):
	def on_init(self):
		self.name = "Occult Blast"
		self.tags = [Tags.Dark, Tags.Holy, Tags.Arcane, Tags.Sorcery, Tags.Blood] ##Maybe remove blood? Though it functions very differently from drain pulse.
		self.asset = ["TcrsCustomModpack", "Icons", "occult_blast"]
		self.level = 5 ##Level 5-6. Its self-damage is extremely high so it's a bit situational. You'll almost treat it like a blood spell.
		##When its radius doesn't grow it's quite reasonable, dealing less damage and having less aoe than flame burst and drain pulse. If you have an ally-maker staff though...
		self.range = 0
		self.max_charges = 5
		self.damage = 25
		self.dtypes = [Tags.Dark, Tags.Holy, Tags.Arcane]
		self.radius = 7
		
		self.upgrades['purestriker'] = (1, 5, "Purestriker", "No longer deals dark damage, but gains 1 radius for each enemy killed.")
		self.upgrades['nightmare'] = (1, 5, "Nightmarish Blast", "No longer deals holy damage, but gains 3 radius for each ally killed.")
		self.upgrades['twilight'] = (1, 2, "Twilight", "No longer deals arcane damage, and no longer deals self-damage.")
		self.upgrades['spirits'] = (1, 4, "Call Spirits", "Units killed summon a ghost of that element in the ring. The caster takes 1 damage for each ghost summoned.")

	def get_description(self):
		return ("Deal {damage} [Dark], [Holy], or [Arcane] in concentric rings around the caster, 1 for each radius. The damage cycles between the three types for each ring.\n" +
				"The caster takes 2 damage multiplied by the total number of rings.\nFor each ally killed the ring gains 1 radius.").format(**self.fmt_dict())

	def cast(self,x,y):
		if self.get_stat('purestrike'):
			self.dtypes = [Tags.Holy, Tags.Arcane]
		elif self.get_stat('nightmare'):
			self.dtypes = [Tags.Dark, Tags.Arcane]
		elif self.get_stat('twilight'):
			self.dtypes = [Tags.Holy, Tags.Dark]
		index_dtype = random.randint(0,len(self.dtypes)-1)
		
		temp_radius = 1
		final_radius = self.get_stat('radius')
		while temp_radius <= final_radius:
			dtype = self.dtypes[index_dtype]
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
						self.caster.level.deal_damage(x, y, 1, dtype, self)

			if not self.get_stat('twilight'):
				self.caster.level.deal_damage(x, y, 2, dtype, self)
			temp_radius += 1
			index_dtype += 1
			if index_dtype >= len(self.dtypes):
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

class TidesofWoe(Spell):
	def on_init(self):
		self.name = "Tides of Woe"
		self.tags = [Tags.Dark, Tags.Lightning, Tags.Ice, Tags.Sorcery]
		self.level = 1
		self.range = 5
		self.max_charges = 5
		self.damage = 15
		
		self.upgrades['box'] = (1, 0, "Box of Woe", "For each 150 damage dealt by this spell summon a box of woe at the target location.")

	def get_description(self):
		return ("Deal [{damage}:damage] of 1 randomly chosen damage type from: [Lightning], [Ice], or [Dark] damage to enemies in a cone. "
				"At the end of your next turn automatically cast this again dealing one of the other types.").format(**self.fmt_dict())

	def cast(self,x,y):
		points = self.get_impacted_tiles(x,y)
		for p in points:
			dtype = random.choice([Tags.Ice, Tags.Lightning, Tags.Dark])
			self.caster.level.deal_damage(p.x, p.y, self.get_stat('damage'), dtype, self)
		yield
	
	def get_impacted_tiles(self, x, y):
		start = Point(self.caster.x, self.caster.y)
		target = Point(x, y)
		main_points = self.caster.level.get_points_in_line(start, target)
		end_points = self.caster.level.get_perpendicular_line(self.caster, Point(x, y), 3)
		for p in self.caster.level.get_points_in_line(main_points[1], end_points[0]):
			main_points.append(p)
		for q in self.caster.level.get_points_in_line(main_points[1], end_points[-1]):
			main_points.append(q)

		return main_points[1:]

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
		self.asset = ["TcrsCustomModpack", "Icons", "idol_of_depths_icon"]
		self.level = 4 #Level 5 probably? Similar to flock of eagles + mini restless dead
		
		self.range = 3
		self.max_charges = 1
		self.minion_health = 25
		self.minion_damage = 8
		self.num_summons = 4
		self.must_target_empty = True
		self.must_target_walkable = True

		self.upgrades['archerfish'] = (1, 4, "Archerfish", "Fishmen are replaced by Archerfish men which have long ranged ice attack with a cooldown.")
		self.upgrades['catfish'] = (1, 2, "Catfish", "Fishmen are replaced by Catfish men which reincarnate once upon dying, and deal dark damage.")
		self.upgrades['stonefish'] = (1, 3, "Stonefish", "Fishmen are replaced by Stonefish which have a ranged attack, burrowing, and more resistances.")

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
		if self.get_stat('stonefish'):
			unit = StoneFish()
			unit.max_hp = 25
			return unit
		elif self.get_stat('catfish'):
			return FishmanCat()
		elif self.get_stat('archerfish'):
			return FishmanArcher()
		else:
			return Fishman()

	def get_extra_examine_tooltips(self):
		stone = StoneFish()
		stone.max_hp = 25
		return [IdolDepths(), Fishman(), self.spell_upgrades[0], FishmanArcher(), self.spell_upgrades[1], FishmanCat(), self.spell_upgrades[2], stone]

	def get_description(self):
		return ("Summons [{num_summons}:num_summons] fishmen, who are worshipping an Idol of the Depths.\n"
				"The Idol debuffs one random enemy each turn causing it to spawn a fishman on death. "
				"Each fishman has the max hp of the enemy that spawned it, with a minimum of [{minion_health}_HP:minion_health],"
				"and deals [{minion_damage}_physical:physical] damage in melee.").format(**self.fmt_dict())

class HasteDamageVersion(Buff):
	def on_init(self):
		self.name = "Rage Awakened"
		self.buff_type = BUFF_TYPE_BLESS
		self.color = Tags.Chaos.color
		self.stack_type = STACK_NONE
		self.asset = ["TcrsCustomModpack", "Icons", "buff_haste"]
		self.owner_triggers[EventOnDamaged] = self.on_damage

	def on_damage(self, damage_event): ##Unstable can crash the game.
		if not damage_event.unit.cur_hp > 0:
			return
		if self.owner.is_alive():
			self.owner.advance()

def Berserker():
	unit = Unit()
	unit.asset = ["TcrsCustomModpack", "Units", "berserker"]
	unit.sprite.char = 'B'
	unit.sprite.color = Color(255, 110, 100)
	unit.name = "Berserker"
	unit.description = "A crazed demon which attacks friend and foe."
	unit.max_hp = 113
	unit.spells.append(LeapAttack(damage=14, damage_type=Tags.Physical, range=8, is_leap=False))
	unit.spells.append(SimpleMeleeAttack(damage=14, trample=True))
	unit.tags = [Tags.Demon, Tags.Chaos]
	return unit

class CallBerserker(Spell):
	def on_init(self):
		self.name = "Call Berserker"
		self.tags = [Tags.Chaos, Tags.Conjuration]
		self.asset = ["TcrsCustomModpack", "Icons", "berserker_icon"]
		self.level = 2 ##Unbelievably well stated for its level, don't use it where it can hit you. Level 3? It's much stronger than bear
		
		self.range = 13
		self.max_charges = 6
		self.minion_health = 113
		self.minion_damage = 13
		self.minion_range = 8
		self.must_target_walkable = True

		self.upgrades['requires_los'] = (-1, 4, "Blindcasting", "Call Berserker can be cast without line of sight")
		self.upgrades['haste'] = (1, 2, "Rage Awakened", "Berserkers takes a turn when it takes damage.")
		self.upgrades['temporary'] = (1, 4, "Pacification", "The berserk status now lasts for [10:duration] turns instead of being permanent. Minion duration lowers this number.")
		
	def get_description(self):
		return ("Summon a berserker, a crazed [demon] which is permanently berserk.\n"
				"The Berserker has [{minion_health}_HP:minion_health] and deals [{minion_damage}_physical:physical] damage with its attacks.\n"
				"The Berserker has both a charging attack with a range of [{minion_range}_tiles:minion_range] and a melee attack.\n"
				"The Berserker will continue fighting after the realm is cleared, until it is killed.\nIt will attack you.").format(**self.fmt_dict())
				##TODO Clicking somewhere after realms are cleared will make you autowalk and the berserker will kill you instantly. Probably unsolveable lmao.
				##Consider making berserkers explode when the realm clears, or something like that?

	def cast(self, x, y):
		unit = Berserker()
		apply_minion_bonuses(self, unit)
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
		if self.get_stat('haste'):
			unit.apply_buff(HasteDamageVersion())

		#u = self.caster.level.get_unit_at(x, y)
		#if u.name == "Berserker":
		#	u.remove_buff(BerserkBuff)

		yield

class ChaosBolt(Spell):
	def on_init(self):
		self.name = "Chaotic Bolt"
		self.tags = [Tags.Chaos, Tags.Sorcery]
		self.level = 3 ##Trying to aim for level 3, to make a level 3 chaos spell as there are only level 2 and 4.
		self.asset = ["TcrsCustomModpack", "Icons", "chaosbolt"]

		self.range = 11
		self.radius = 4
		self.max_charges = 15
		self.damage = 12

		self.upgrades['imp'] = (1, 3, "Improviser", "Casts your Improvise at enemy units instead of arcing.") ##Very strong with swarm improviser, perhaps increase cost?
		self.upgrades['extra'] = (1, 4, "Comprehensive", "Add Arcane and Dark damage types.") ##TODO add holy damage, and make it do both types of damage because that's cool
		
	def get_description(self):
		return ("Shoots a bolt of chaotic energy in a line. The bolt deals {damage} [fire], [lightning], or [physical] to units, "
				"and each unit in the bolt's path arcs a separate bolt within [{radius}_tile:radius] to one more unit.").format(**self.fmt_dict())

	def cast(self, x, y):
		tiles = self.get_impacted_tiles(x,y)
		dtypes = [Tags.Fire, Tags.Lightning, Tags.Physical]
		if self.get_stat('extra'):
			dtypes.append(Tags.Arcane)
			dtypes.append(Tags.Dark)
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
		self.name = "Machination"
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
		self.tags = [Tags.Ice, Tags.Metallic, Tags.Sorcery, Tags.Conjuration]
		self.level = 3 ##Aiming for level 3 or 4. 3 Competes with lightning spire, and silver spear. 4 with fewer metallic spells. Maybe push this to 5?
		self.asset = ["TcrsCustomModpack", "Icons", "cold_machination"]

		self.range = 8
		self.can_target_empty = False
		self.max_charges = 5
		self.damage = 30
		self.units = [WormBallIron(5), DancingBlade(), GlassMushboom(), MetalMantis(), SteelSpider(), 
					Golem(), Gargoyle(), GolemClay(), WormBallIron(50), SpikeBall(), IronFiend()]
		
		##Some sort of anti-construct upgrade that adds a damage type that constructs don't resist? It's not designed to be good at killing constructs.
		self.upgrades['smith'] = (1, 2, "Blacksmith", "Cast your Armageddon Blade on the first construct made from each cast of the spell.")
		self.upgrades['garden'] = (1, 5, "Bizarrtificer", "Also deals [Arcane] damage. Instead of constructs, cast your psychic seedling on random tiles for each 10 hp the target had.")
		self.upgrades['accumulation'] = (1, 5, "Accumulation", "Now summons units if the target dies within [4:duration] turns. Any damage taken over this period is added to the construct's max hp.")

	def get_description(self):
		return ("Deals [{damage}_ice:ice] to target unit. If it dies it spawns random constructs around it. "
				"The total hp of constructs is equal to the max hp of the unit.\n"
				"[Construct] or [Metallic] targets summon twice as many units.").format(**self.fmt_dict())

	def cast_instant(self, x, y):
		#print("Cast Machination")
		u = self.caster.level.get_unit_at(x,y)
		if u == None:
			return
		if self.get_stat('accumulation'):
			duration = self.get_stat('duration',base=4)
			u.apply_buff(MachinationBuff(self), duration)
		u.deal_damage(self.get_stat('damage'), Tags.Ice, self)
		if self.get_stat('garden'):
			u.deal_damage(self.get_stat('damage'), Tags.Arcane, self)
		if not u.is_alive() and not self.get_stat('accumulation'):
			self.convert_unit(u, u.max_hp)

	def convert_unit(self, unit, sum_damage):
		u = unit
		damage = sum_damage
		if Tags.Metallic in u.tags or Tags.Construct in u.tags:
			damage = damage * 2
			
		if self.get_stat('garden'):
			count = damage // 10
			tiles = [t for t in self.caster.level.iter_tiles() if t.is_floor()]
			for i in range(count): ##TODO check if this crashes when every single floor is occupied.
				spell = self.caster.get_or_make_spell(BrainSeedSpell)
				t = random.choice(tiles)
				self.caster.level.act_cast(self.caster, spell, t.x, t.y, False)
		else:
			index = random.randint(0, len(self.units)-1)
			first = True
			while damage > 5: ##This must be higher than the lowest hp in the list to avoid infinite looping, in this case 5
				construct = copy.deepcopy(self.units[index])
				#print(construct.name)
				#print(damage)
				if damage > construct.max_hp:
					damage -= construct.max_hp
					self.summon(construct, Point(u.x,u.y), sort_dist=False)
					index = random.randint(0, len(self.units)-1)
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
		self.spell.summon(unit, self.owner)
		if self.spell.get_stat('trickery'):
			unit.apply_buff(Skullbuffery(self.spell), self.spell.get_stat('duration',base=3)  + self.spell.get_stat('minion_duration', base=3))

class Skulldiggery(Spell):
	def on_init(self):
		self.name = "Skulldiggery"
		self.tags = [Tags.Dark, Tags.Nature, Tags.Enchantment, Tags.Conjuration]
		self.level = 2 ##Level 2-3? Well stated for lvl2 spell, but not the easiest spell to trigger. With 'lasting' it will cost 4-5 and be comparable to petrify + golem
		self.asset = ["TcrsCustomModpack", "Icons", "skulldiggery"] ##Fix the pixel at the joint that moves up and down, it's too thin

		self.range = 10
		self.max_charges = 10
		self.can_target_empty = False
		self.quick_cast = 1
		
		example = SkullWorm()
		self.minion_health = example.max_hp
		self.minion_damage = example.spells[0].damage

		self.upgrades['betrayal'] = (1, 1, "Betrayal", "Also berserk the target for [1:duration] turn.")
		self.upgrades['lasting'] = (1, 2, "Dishonesty", "The buff now lasts for [10:duration] turns instead of 1.")
		self.upgrades['trickery'] = (1, 2, "Trickery", "The Skullsnake gains this buff for [3:duration] turns when it spawns. This scales with both duration and minion duration")
		
	def get_description(self):
		return ("Target unit gains Skulldiggery for 1 turn. If it dies spawn a skullsnake at its location. "
				"If it was an ally, it also reincarnates.\nCasting this spell takes half of your turn.\n"
				"Skullsnakes are burrowing melee units with [{minion_health}_HP:minion_health] and deal [{minion_damage}_physical:physical] damage.\n").format(**self.fmt_dict())

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

		self.range = 5
		self.max_charges = 2
		self.must_target_empty = True
		self.minion_health = 25
		self.minion_damage = 5
		self.shot_cooldown = 3

		self.upgrades['spawn_eyes'] = (1, 3, "Independent Oversight", "Each time the Eyedra dies, it casts your floating eye.")
		self.upgrades['draconic'] = (1, 1, "Dragonic Lineage", "The Eyedra's gazing attack now benefits from bonuses to breath damage.")
		self.upgrades['durable'] = (1, 3, "Durable", "Instead of dying at 0 eye-heads, it becomes headless for 5 turns. If it survives, Summon Eyedra is recast at its location.")

	def get_description(self):
		return ("Summon the Eyedra, a stationary minion with 4 eye-heads. For each head it can attack one unit in line of sight for [{minion_damage}_arcane:arcane] damage. \n"
				"The Eyedra loses one head each time it dies, reviving on its tile. Casting this spells again replaces the Eyedra and adds another head, up to 6."
				"It gains 1 head for each shot cooldown below 3.\nYou can only have one Eyedra, it cannot be given reincarnations.").format(**self.fmt_dict())


	def cast_instant(self, x, y):
		unique_unit = [u for u in self.caster.level.units if not are_hostile(self.caster, u) and u.name == "The Eyedra"]
		target = Point(x,y)
		if unique_unit == []:
			heads = 4 + (3 - self.get_stat('shot_cooldown'))
			if heads > 6: #Update to higher numbers as I make bigger sprites
				heads = 6
		else:
			old_unit = unique_unit[0]
			if old_unit.heads < 6:
				heads = old_unit.heads + 1
			else:
				heads = old_unit.heads
			old_unit.kill(trigger_death_event=False)
		unit = Eyedra(heads)
		unit.buffs.append(EyedraReincarnation(unit.heads,self))
		if self.get_stat('draconic'):
			for s in unit.spells:
				if s.name == "Eye Bolt":
					s.damage += self.get_stat('breath_damage', base=4)
		apply_minion_bonuses(self, unit)
		self.summon(unit, target)


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
	
		self.range = 12
		self.max_charges = 20
		self.minion_health = 25
		self.minion_damage = 15
		
		self.upgrades['erupt'] = (1, 1, "Volcanic Heart", "If the orb ends over a chasm, you cast your Volcanic Eruption on said chasm.")
		self.upgrades['cleave'] = (1, 2, "Angelic Sword", "The orb gains the cleaving sword of your Call Seraph spell instead of a simple melee attack.")
		self.upgrades['spear'] = (1, 5, "Argent Spear", "The orb has your silver spear on a 2 turn cooldown.")
		self.upgrades['orb_walk'] = (1, 1, "Quicksilver Coating", "Targeting an existing Unbreakable Orb destroys it, summoning a Quicksilver Geist.")

	def get_description(self):
		return ("Summons an Unbreakable Orb which attacks as it moves, dealing [{minion_damage}_physical:physical] damage to one unit in melee range.\n"
				"The orb has no will of its own, each turn it will float one tile towards the target.\n"
				"The orb is immune to all elements.").format(**self.fmt_dict())
	
	def on_orb_move(self, orb, next_point):
		pass

	def on_make_orb(self, orb):
		#print(self.caster.name)
		orb.name = "Unbreakable Orb"
		orb.asset =  ["TcrsCustomModpack", "Units", "shield_orb_axe"]
		orb.tags.append(Tags.Metallic)

		if self.get_stat('cleave'):
			melee = copy.deepcopy(SeraphimSwordSwing())
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
			orb.spells.append(SimpleMeleeAttack(damage=15, damage_type=Tags.Physical))
		else:
			orb.spells.append(SimpleMeleeAttack(damage=15, damage_type=Tags.Physical))

	def on_orb_collide(self, orb, next_point):
		orb.level.show_effect(next_point.x, next_point.y, Tags.Physical)
		if self.get_stat('erupt') and self.owner.level.tiles[orb.x][orb.y].is_chasm: ##TODO Seems to work, check more. Something to do with collision vs orb dying
			eruption = self.caster.get_or_make_spell(Volcano)
			self.caster.level.act_cast(self.caster, eruption, orb.x, orb.y, pay_costs=False)
		yield

	def on_orb_walk(self, existing):
		x = existing.x
		y = existing.y
		existing.kill()
		geist = QuicksilverGeist()
		spell = self.caster.get_or_make_spell(MercurizeSpell)
		geist.turns_to_death = spell.get_stat('minion_duration', base=32)
		apply_minion_bonuses(self, geist)
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
		self.name = "Gooify"
		self.owner_triggers[EventOnDeath] = self.on_death
		
	def on_death(self, evt):
		slime_spell = self.spell.owner.get_or_make_spell(SlimeformSpell)
		slime_buff = SlimeformBuff(slime_spell)
		
		spawn_funcs = [GreenSlime]
		if slime_spell.get_stat('fire_slimes'):
			spawn_funcs.append(RedSlime)
		if slime_spell.get_stat('ice_slimes'):
			spawn_funcs.append(IceSlime)
		if slime_spell.get_stat('void_slimes'):
			spawn_funcs.append(VoidSlime)
		
		spawn_func = random.choice(spawn_funcs)
		unit = slime_buff.make_summon(spawn_func)
		slime_spell.summon(unit, target=Point(self.owner.x, self.owner.y))

class PoisonousGas(Spell): #Based on "Bleezy"'s idea of a spell with constant volume.
	def on_init(self):
		self.name = "Poisonous Gas"
		self.level = 3 ##Aiming for 3 as a poison spell stronger than toxin burst but also lets you combo with mushbooms
		self.tags = [Tags.Nature, Tags.Enchantment]
		self.asset = ["TcrsCustomModpack", "Icons", "poisonousgas"]

		self.range = 10
		self.max_charges = 5
		self.radius = 25
		self.damage = 10
		self.duration = 6

		self.upgrades['slime'] = (1, 4, "Gooify", "All non [slime] units in the initial cast area get the gooify debuff, spawning a slime when they die. Inherits slime form upgrades.")
		self.upgrades['mercury'] = (1, 4, "Phenylmercury", "Each cloud gives your mercurize debuff to the first unit it damages for [5:duration] turns.")
		self.add_upgrade(FungalSpores())

	def get_description(self):
		return ("Creates poison clouds in a [{radius}_tile:radius] tile area for 6 turns. The area starts from the center tile and spreads in each direction.\n"
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
		remaining = self.radius
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

			possible_targets = self.owner.level.units ##TODO line of sight, works weirdly with cone spells
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

		self.range = 0
		self.max_charges = 2
		self.duration = 5
		
		self.upgrades['howitzer'] = (1, 4, "Howlitzer", "Instead of casting a sorcery, casts your wolf spell at the furthest target.")
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

		self.range = 5
		self.max_charges = 1
		self.minion_health = 250
		self.minion_damage = 30
		self.minion_range = 6
		
		#[''] TODO implement, maybe switch zap with some bloody electric robot that needs constant charging with your life force / zap it?
		#self.upgrades['zap'] = (1, 0, "Pacemaker", "The Beast no longer freezes but must be struck by lightning damage every 3 turns or it is stunned.")
		self.upgrades['exsanguinate'] = (1, 3, "Bloodstarved Beast", "The Beast gains your exsanguinate spell on an 8 turn cooldown.")
		self.upgrades['unchained'] = (1, 4, "Unchained", "The Beast no longer freezes, but it only lasts [25:duration] turns.")
		self.upgrades['hunger'] = (1, 4, "Endless Hunger", "The Beast no longer freezes, but it takes 15 holy damage each turn and has no regeneration if 3 turns pass without it killing.")

	def get_description(self):
		return ("Summons an Ice-Cursed Beast, who thaws in 3 turns. Each time it kills a unit it refreezes. \n"
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
	def on_init(self):
		self.buff_type = BUFF_TYPE_BLESS
		self.name = "Cloudwalking"
		self.color = Tags.Lightning.color
		self.resists[Tags.Lightning] = 75
		self.resists[Tags.Ice] = 75

class Cloudwalk(Spell):
	def on_init(self):
		self.name = "Cloudwalk"
		self.tags = [Tags.Ice, Tags.Lightning, Tags.Translocation]
		self.level = 3 ##Extremely niche but good with cloud builds like stormcaller. Designed to be better than blink if any clouds are available.
		self.asset = ["TcrsCustomModpack", "Icons", "cloud_walk"]
		self.description = "Teleport to a tile in line of sight which has a Blizzard or Thundercloud on it. Consumes the cloud."
		
		self.range = 99
		self.max_charges = 4
		self.must_target_empty = True
		self.clouds = [BlizzardCloud, StormCloud, RainCloud]

		self.upgrades['requires_los'] = (-1, 3, "Blindcasting")
		self.upgrades['strange'] = (1, 1, "Strange Weather", "Can now target: Fire clouds, Poison clouds, Blood clouds")

	def can_cast(self, x, y): ##Absolute 9000 IQ idea, see if quickcast can be set here so it applies while a spell is being cast.
		if self.get_stat('requires_los'):
			if not self.caster.level.can_see(self.caster.x, self.caster.y, x, y, light_walls=self.cast_on_walls):
				return False
		cloud = self.caster.level.tiles[x][y].cloud
		if type(cloud) in self.clouds:
			#print(cloud)
			cloud = True
		return Spell.can_cast(self, x, y) and self.caster.level.can_move(self.caster, x, y, teleport=True) and cloud

	def cast(self, x, y):
		self.caster.level.tiles[x][y].cloud.kill()
		self.caster.level.act_move(self.caster, x, y, teleport=True)
		yield
		
	def get_targetable_tiles(self):
		x = self.caster.x
		y = self.caster.y
		eligible_p = []
		points = self.caster.level.iter_tiles()
		if self.get_stat('strange'):
			self.clouds = [BlizzardCloud, StormCloud, PoisonCloud, FireCloud]
		for p in points:
			if not self.can_cast(p.x, p.y):
				continue
			cloud = self.caster.level.tiles[p.x][p.y].cloud
			if cloud and (type(cloud), Cloud):
				eligible_p.append(p)
		return eligible_p



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
		return "Store each tag in any spell you cast.\nOn expiration, deals 2 damage of a random type, times the number of tags, to each enemy.\n\nCurrent tags: %d" % num_tags

	def on_cast(self, evt):
		for tag in evt.spell.tags:
			if tag not in self.tags:
				self.tags.append(tag)

	def on_unapplied(self):
		self.owner.level.queue_spell(self.rainbow())

	def rainbow(self):
		enemies = [u for u in self.owner.level.units if are_hostile(self.owner, u)]
		damage = len(self.tags) * 2
		if self.spell.get_stat('scaling'):
			enchdmg = self.spell.get_stat('damage', base=2)
			flatdmg = math.floor(enchdmg / 3)
			enchdmg_pct = self.owner.tag_bonuses_pct[Tags.Enchantment].get('damage', 0)
			pctdmg = math.floor(enchdmg_pct / 25)
			damage += flatdmg
			damage += pctdmg
			#print(flatdmg)
			#print(enchdmg_pct)
			
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
		self.range = 0
		self.duration = 6

		self.upgrades['scaling'] = (1, 4, "Empowered", "Now scales with enchantment damage, dealing 1 more damage per tag for each 3 enchantment damage, and 1 more damage for each 25% damage increase you have.")
		self.upgrades['double'] = (1, 3, "Double Dip", "Deals damage a second time after the first, with a new random damage type.")
		self.upgrades['reroll'] = (1, 1, "Reroll", "If the unit is immune to the random damage, randomly select one more time.")

	def get_description(self):
		return ("Gain Rainbow Seal for [{duration}_turns:duration].\n"
				"When you cast a spell, the seal gains a charge for each unique tag in the spell, e.g. [Fire], [Sorcery], [Chaos], etc.\n"
				"When the seal expires, each enemy takes 2 damage multiplied by the number of charges, of a random type.\n"
				"Recasting the spell will expire the current seal and create a new one.").format(**self.fmt_dict())

	def cast_instant(self, x, y):
		self.caster.apply_buff(RainbowSealBuff(self), self.get_stat('duration'))


class ShrapnelBreath(BreathWeapon):
	def on_init(self):
		self.name = "Shrapnel Breath"
		self.damage = 9
		self.damage_type = Tags.Physical

	def get_description(self):
		return "Breathes a cone of shrapnel dealing %d [physical] damage" % self.damage

	def per_square_effect(self, x, y):
		self.caster.level.deal_damage(x, y, self.damage, self.damage_type, self)

class SteelFangsBuff(Buff):
	def __init__(self, spell):
		Buff.__init__(self)
		self.spell = spell

	def on_init(self):
		self.name = "Steel Fangs"
		self.stack_type = STACK_INTENSITY
		self.buff_type = BUFF_TYPE_BLESS
		self.color = Tags.Dragon.color
		self.hp_bonus = 1
		self.damage = 1
		self.breath_damage = 1

	def on_applied(self, owner):
		self.damage = self.spell.get_stat('breath_damage')
		self.breath_damage = self.spell.get_stat('damage')
		owner.cur_hp += self.spell.get_stat('hp_bonus')
		owner.max_hp += self.spell.get_stat('hp_bonus')
		for spell in self.owner.spells:
			if not hasattr(spell, 'damage'):
				continue
			if isinstance(spell, BreathWeapon):
				spell.damage += self.breath_damage
			else:
				if self.spell.get_stat('steal') and isinstance(spell, SimpleMeleeAttack) and not spell.drain:
					spell.drain = True
				spell.damage += self.damage



class SteelFangs(Spell):
	def on_init(self):
		self.name = "Steel Fangs"
		self.level = 3 ##Tentative 4, but dragon roar is just way stronger overall, affects the whole map, etc. Making it last forever as a compromise.
		self.asset = ["TcrsCustomModpack", "Icons", "steelfangs"] ##Variation of Drakentooth
		self.tags = [Tags.Enchantment, Tags.Dragon, Tags.Metallic]
		
		self.can_target_empty = False
		self.range = 99
		self.max_charges = 10
		self.breath_damage = 10
		self.damage = 10
		self.hp_bonus = 25
		self.unit_tags = [Tags.Dragon, Tags.Metallic]

		self.upgrades['breath'] = (1, 5, "Heart of the Drake", "Gives metallic units a breath attack that deals physical damage.")
		self.upgrades['soul'] = (1, 4, "Steel Thy Soul", "Non [arcane:arcane] units gain the Faetouched modifier.")
		self.upgrades['steal'] = (1, 2, "Stealing Fangs", "Gives simple melee attacks a life stealing effect.")
		
	def get_description(self):
		return ("Target minion gains [{damage}_damage:damage] to their breath attack, scaling with this spell's damage stat, "
				"and its other attacks gain [{breath_damage}_damage:breath_damage] bonus damage scaling with this spell's breath damage.\n "
				"Target minion then gains the [metallic] and [dragon] tags, and 25 max hp.").format(**self.fmt_dict())

	def cast(self, x, y):
		unit = self.caster.level.get_unit_at(x, y)
		if unit:
			buff = SteelFangsBuff(self)
			if not Tags.Metallic in unit.tags: ##Extremely niche problem, but if resistances are temporarily lowered, this will permanently raise them.
					unit.tags.append(Tags.Metallic)
					if unit.resists[Tags.Fire] < 50:
						unit.resists[Tags.Fire] = 50
					if unit.resists[Tags.Physical] < 50:
						unit.resists[Tags.Physical] = 50
					if unit.resists[Tags.Ice] < 75:
						unit.resists[Tags.Ice] = 75
					if unit.resists[Tags.Lightning] < 100:
						unit.resists[Tags.Lightning] = 100
			else:
				if self.get_stat('breath'):
					breath_weapon = False
					for spell in unit.spells:
						s_type = type(spell)
						if (s_type == BreathWeapon):
							breath_weapon = True
					if not breath_weapon:
						buff.spells.append(ShrapnelBreath())
			if not Tags.Dragon in unit.tags:
					unit.tags.append(Tags.Dragon)
			if not Tags.Arcane in unit.tags and self.get_stat('soul'):
				unit.Anim = None
				BossSpawns.apply_modifier(Faetouched, unit)
			unit.apply_buff(buff)
		yield

class Leapfrog(Spell):
	def on_init(self):
		self.name = "Leapfrog"
		self.level = 3 #Level 2 perhaps? Extremely specific in how it works, like aether swap, but limited in how it targets. Actually very strong in practice, level 3
		self.tags = [Tags.Nature, Tags.Translocation]
		self.asset = ["TcrsCustomModpack", "Icons", "leapfrog"]
		self.description = "Teleport to the opposite side of a unit, maintaining relative distance. Destination tile must be empty."
		
		self.range = 16
		self.max_charges = 15
		##Implement line of sight checking for the custom can_cast def
		self.upgrades['quick_cast'] = (1, 3, "Quickcast", "Casting Leapfrog does not end your turn. Consumes 1 extra charge each cast.")
		self.upgrades['wolf'] = (1, 1, "Leapdog", "Cast your wolf at the spot you jumped from. Consumes 1 extra charge each cast.")
		self.upgrades['walls'] = (1, 3, "Parkour", "Can now be cast on, or across walls.")
		
	def get_end_tile(self, x, y):
		newX = self.caster.x + (x - self.caster.x) * 2
		newY = self.caster.y + (y - self.caster.y) * 2
		newPoint = Point(newX, newY)
		if self.caster.level.is_point_in_bounds(newPoint):
			return newPoint

	def get_impacted_tiles(self, x, y): ##This may have edge problems. See if anything breaks it.
		tile = self.get_end_tile(x, y)
		if tile != None:
			return [tile]
		else:
			return [Point(self.caster.x, self.caster.y)]

	def can_cast(self, x, y):
		tile = self.get_end_tile(x, y)
		if tile == None:
			return False
		if self.caster.level.tiles[tile.x][tile.y].is_chasm:
			return False
		if self.caster.level.tiles[tile.x][tile.y].is_wall():
			return False
		if self.caster.level.get_unit_at(tile.x, tile.y):
			return 
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
		
class ChainJump(Upgrade):
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
		self.owner.level.queue_spell(self.remove_quickcast())

	def remove_quickcast(self):
		self.spell.quick_cast = 0
		self.spell = None
		yield

class KnightlyLeap(Spell):
	def on_init(self):
		self.name = "Cavalier's Warp"
		self.level = 2 #This spell is actually so bad I'm just giving it quickcast for free, and removing the damage. It makes you immune to melee units at a certain angle, okay.
		self.tags = [Tags.Holy, Tags.Translocation] ##This is weird but not impossible to combine with cantrip cascade, for now it's not a sorcery
		self.asset = ["TcrsCustomModpack", "Icons", "knightlyleap"]

		self.range = 3
		self.max_charges = 10
		self.quick_cast = True
		self.requires_los = False
		self.damage = 5

		#self.add_upgrade(ChainJump()) ##This type of conditional quickcast effect is very cool, but this spell is awful, it doesn't need a condition
		self.upgrades['shield'] = (1, 2, "Knight's Shield", "Gain 1 shield if you targeted a unit, up to 4.")
		self.upgrades['mole'] = (1, 4, "Burrowing Jump", "Can target walls, melting them if necessary. (It is possible to trap yourself)")
		
	def get_description(self):
		return ("Teleport to target location exactly 3 tiles away in an L-shape.\n"
				"If there is a unit there, it takes [{damage}_holy:holy] damage, and you attempt to displace it one tile, then teleport to its tile."
				" If it can't be moved or did not die to the damage, you don't teleport.").format(**self.fmt_dict())

	def get_targetable_tiles(self):
		tiles = []
		#r = self.get_stat('range') - 1 ##This can scale but it's kind of hard to decide in which direction the L should go. Keep it at range 3 for now.
		r = 2
		base_tiles = []
		base_tiles.append(Point(self.caster.x, self.caster.y + 1))
		base_tiles.append(Point(self.caster.x + 1, self.caster.y))
		base_tiles.append(Point(self.caster.x, self.caster.y - 1))
		base_tiles.append(Point(self.caster.x - 1, self.caster.y))
		flip = True
		while base_tiles != []: ##TODO remove walls and chasms from green tiles, already aren't castable so it's just a UI problem.
			t = base_tiles.pop(0)
			if not self.caster.level.is_point_in_bounds(t):
				continue
			if flip == True:
				tiles.append(Point(t.x + r, t.y))
				tiles.append(Point(t.x - r, t.y))
				flip = False
			else:
				tiles.append(Point(t.x, t.y + r))
				tiles.append(Point(t.x, t.y - r))
				flip = True
		return tiles

		#if self.caster.level.tiles[t.x][t.y].is_chasm: ##These have to be applied to all four options.
		#	continue
		#if self.caster.level.tiles[t.x][t.y].is_wall():
		#	continue

	def can_cast(self, x, y):
		tiles = self.get_targetable_tiles()
		p = Point(x,y)
		if self.caster.level.tiles[p.x][p.y].is_chasm:
			return False
		if self.caster.level.tiles[p.x][p.y].is_wall() and not self.get_stat('mole'):
			return False
		if p in tiles:
			return Spell.can_cast(self, x, y)

	def cast(self, x, y):
		u = self.caster.level.get_unit_at(x, y)
		if u != None:
			if self.get_stat('shield'):
				if self.caster.shields < 5:
					self.caster.shields += 1
			self.caster.level.deal_damage(x, y, self.get_stat('damage'), Tags.Holy, self)
			if not u.is_alive():
				self.caster.level.act_move(self.caster, x, y, teleport=True)
			else:
				genfunc = self.caster.level.get_adjacent_points(u, filter_walkable=True)
				adjacent_tiles = []
				for t in genfunc:
					adjacent_tiles.append(t)
				if adjacent_tiles != []: ##TODO check more tiles for displacement, right now it just checks one.
					tile = random.choice(adjacent_tiles)
					self.caster.level.act_move(u, tile.x, tile.y, teleport=False)
		if self.caster.level.tiles[x][y].is_wall() and self.get_stat('mole'):
			self.caster.level.make_floor(x, y)
		if self.caster.level.can_move(self.caster, x, y, teleport=True):
			self.caster.level.act_move(self.caster, x, y, teleport=True)
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
			unit = StarfireSnakeGiant()
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
		self.tags = [Tags.Fire, Tags.Lightning, Tags.Conjuration, Tags.Chaos]
		self.level = 3 ##Aiming for level 3, but the scaling on spawning snakes is quite strong, making them timed will help. The regular minion is reasonable.
		##Honestly so weird to scale these tags it can probably get more charges or something. None of these scale at all.
		self.asset = ["TcrsCustomModpack", "Icons", "chaotic_snake_icon"]

		self.range = 5
		self.max_charges = 3
		self.minion_health = 36
		self.minion_damage = 8
		self.minion_duration = 8

		self.upgrades['storm'] = (1, 4, "Storm Beast", "Gains 5 max hp when it witnesses a Lightning or Ice spell.")
		self.upgrades['slazephan'] = (1, 6, "Scholar of Scales", "If you do not have an allied Slazephan, summon Slazephan beside the wizard.")
		self.upgrades['yharnum'] = (1, 4, "Yharnanmite Monster", "Instead of small snakes, summon giant fire snakes for each 36 max hp, with 4 times as much life and duration.")

	def get_description(self):
		return ("Summons a Chaotic Snakeball, which gains max hp when it takes: [Physical], [Fire], or [Lightning] damage, equal to the damage taken.\n"
				"The Snakeball has [{minion_health}_HP:minion_health] and deals [{minion_damage}_damage:minion_damage] with its melee attack.\n"
				"On death it summons 1 snake for each 9 max hp it had. These snakes last [{minion_duration}_turns:minion_duration] turns.").format(**self.fmt_dict())
	
	def get_extra_examine_tooltips(self):
		return [ChaosBeast(), Snake(), FireSnake(), GoldenSnake(), self.spell_upgrades[0], self.spell_upgrades[1], SerpentPhilosopher(), self.spell_upgrades[2], StarfireSnakeGiant()]

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
		units = [u for u in self.owner.level.get_units_in_ball(self.owner, 3) if (Tags.Dark in u.tags or Tags.Undead in u.tags or u.name == "Wizard")]
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
			self.owner.apply_buff(FearBuff(), 1)

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
		self.tags = [Tags.Nature, Tags.Dark, Tags.Conjuration]
		self.level = 4 ##Immediately comparable to bear. Might be a level 4 and give it more charges with similar damage? Bear does attack twice. Cooler upgrades.
		self.asset = ["TcrsCustomModpack", "Icons", "cowardly_lion_icon"]

		self.must_target_walkable = True
		self.range = 5
		self.max_charges = 3
		self.minion_health = 100
		self.minion_damage = 19

		self.upgrades['pride'] = (1, 5, "Pride", "Your Lion can summon 1: Fire, Ice, or Star Lion on a 10 turn cooldown.")
		self.upgrades['roar'] = (1, 5, "Dreadful Roar", "Your Lion gains your wave of dread spell on a 10 turn cooldown.")
		self.upgrades['fearless'] = (1, 5, "Fearless", "Your Lion is not afraid of [Dark] or [Undead] units, and gains a holy leaping attack with 6 range.")

	def get_description(self):
		return ("Call forth a cowardly lion, who gains the fear debuff if any [dark], or [undead] units are within 3 tiles and the wizard is not within 3 tiles.\n"
				"Cowardly Lions have [{minion_health}_HP:minion_health] and an attack which deals [{minion_damage}_physical:physical] damage.").format(**self.fmt_dict())

	def get_extra_examine_tooltips(self):
		return [CowardlyLion(), self.spell_upgrades[0], RedLion(), IceLion(), StarLion(), self.spell_upgrades[1], self.spell_upgrades[2]]

	def cast(self, x, y):
		unit = CowardlyLion()
		if self.get_stat('fearless'):
			leap = LeapAttack(damage=self.get_stat('minion_damage'), range=self.get_stat('minion_range',base=6), is_leap=True, damage_type=Tags.Holy)
			unit.spells.insert(0, leap)
		else:
			unit.apply_buff(CowardlyBuff(self))
		if self.get_stat('pride'):
			lion = random.choice([RedLion, IceLion, StarLion])
			summon_lion = SimpleSummon(spawn_func=lion, num_summons=1, cool_down=10)
			unit.spells.insert(0,summon_lion)
		if self.get_stat('roar'):
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

		self.bonus = 5
		self.range = 10
		self.duration = 5
		self.max_charges = 5
		self.can_target_empty = False
		self.can_target_self = True

		self.upgrades['cleave'] = (1, 5, "Cleaver", "If you are within the group, and at least 5 enemies are connected, cast your Death Cleave spell.")
		self.upgrades['extend'] = (1, 3, "Extend Buffs", "Each stack of the buff also gives 2 duration and 2 minion duration to the next spell.")
		self.upgrades['minion'] = (1, 3, "Empower Minions", "Each stack of the buff also gives 3 minion health and 3 minion damage to the next spell.")

	def get_description(self):
		return ("All enemy units in a connected group lose 5 damage. Each enemy then gives one connected ally 5 damage."
				"The buffs last [{duration}_turns:duration] and wear off after 1 spell or attack. The buffs and debuffs can stack.").format(**self.fmt_dict())

	def cast(self, x, y):
		tiles = self.caster.level.get_connected_group_from_point(x, y, check_hostile=None)
		allies = []
		enemies = []
		for t in tiles:
			u = self.caster.level.get_unit_at(t.x, t.y)
			if are_hostile(self.caster, u):
				enemies.append(u)
				u.apply_buff(Ennervate(), 5)
			else:
				if u.name == "Wizard":
					allies.insert(0,u)
				else:
					allies.append(u)
		
		if allies == []:
			return
		count = len(enemies)
		if count >= 5 and self.get_stat('cleave'):
			spell = self.caster.get_or_make_spell(DeathCleaveSpell)
			self.caster.level.act_cast(self.caster, spell, self.caster.x, self.caster.y, pay_costs=False)
		index = 0
		for i in range(count):
			allies[index].apply_buff(Innervate(self), 5)
			index += 1
			if index == len(allies):
				index = 0
		
		yield
		
	def get_impacted_tiles(self, x, y):
		return self.caster.level.get_connected_group_from_point(x, y, check_hostile=None)


class TreeFormBuff(Buff):
	def __init__(self, spell):
		Buff.__init__(self)
		self.spell = spell
		#self.transform_anim = ["TcrsCustomModpack", "Units", "player_tree_form"]
		#self.asset = ['status', 'lightning_form']
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

		self.range = 0
		self.max_charges = 1
		self.num_targets = 1

		self.upgrades['evil'] = (1, 2, "Spreading Evil", "Gain 75 [Dark] resist during the effect, and summon a ghost nearby you each turn.")
		self.upgrades['fertilize'] = (1, 4, "Fertilize", "Each turn, the first time a [Living] or [Nature] unit dies, cast your Toxic Spore at that location.")
		self.upgrades['uproot'] = (1, 2, "Uproot", "This effect now instead lasts 15 turns and gains 3 turns each time you cast a level 3 or higher nature spell. Does not end when you move.")
		
	def on_applied(self):
		self.owner.transform_anim = ["TcrsCustomModpack", "Units", "player_tree_form"]
		

	def cast(self, x, y):
		if self.get_stat('uproot'):
			self.caster.apply_buff(TreeFormBuff(self), self.get_stat('duration'), base=15)
		else:
			self.caster.apply_buff(TreeFormBuff(self))
		yield

	def get_description(self):
		return ("Each turn, cast your poison sting at up to [{num_targets}:num_targets] random enemy. If the buff lasts more than 5 turns, also cast toxin burst.\n"
				"Gain 100 poison resist during the effect.\nEnds when you move.").format(**self.fmt_dict())


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

class AnimateClutter(Spell): ##TODO this will need to update for evermelting icecube when its name gets restored. Right now it's wrong.
	def on_init(self):
		self.name = "Animate Clutter"
		self.tags = [Tags.Arcane, Tags.Metallic, Tags.Conjuration]
		self.asset = ["TcrsCustomModpack", "Icons", "animate_clutter"]

		self.level = 3
		self.range = 0
		self.max_charges = 5
		self.minion_health = 2
		self.minion_damage = 6
		self.suffixes = ['claw', 'dagger', 'disk', 'fang', 'flag', 'horn', 'hourglass', 'lens', 'orb', 'scale', 'sigil', 'tome']
		self.asset_list = []
		
		self.upgrades['sorcerer'] = (1, 1, "Chromatic Wizard", "Instead of animating trinkets, summon a living scroll for each tag in each spell you know.")
		self.upgrades['selfequip'] = (1, 1, "Piper Linker", "Your animated Pipes and Links equip a copy of themselves.")
		self.upgrades['sigil'] = (1, 1, "Sigilite", "Your sigils can summon their associated unit every 15 seconds.")

		self.tagdict = ScrollConvertor()
		self.tagdict[Tags.Metallic] = MetalShard,LivingMetalScroll()
		self.tagdict[Tags.Chaos] = Improvise,LivingChaosScroll()


	def get_description(self):
		return ("Animate your trinkets into allies. Each trinket is a flying, teleporting, melee attacker which "
				"deals [{minion_damage}_physical:physical] damage and has [{minion_health}_HP:minion_health] and 3 shields.").format(**self.fmt_dict())

	def cast(self, x, y):
		if self.get_stat('sorcerer'):
			for s in self.caster.spells:
				for tag in s.tags:
					if tag in self.tagdict:
						unit = copy.deepcopy(self.tagdict[tag][1])
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

		self.range = 10
		self.max_charges = 10
		self.dmg = 2
		self.can_target_self = False
		self.requires_los = False

		self.upgrades['threeseven'] = (1, 2, "3s and 7s", "Also affects all units whose current hp ends in 3 or 7")
		self.upgrades['prime'] = (1, 1, "Prime Power", "Also affects all units whose current hp is a prime number.")
		self.upgrades['dmg'] = (2, 4, "Potency", "Now deals 4 base damage.")

	def get_description(self):
		return ("Calculate the distance value, X, which is equal to the number of tiles between yourself and target tile.\n"
				"Then for every unit deal 2 [arcane] damage multiplied by X to it, if its current hp is evenly divisible by X. Silences affected units for 3 seconds.").format(**self.fmt_dict())

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
		#print(divisor)
		for unit in units:
			if unit.cur_hp % divisor == 0:
				unit.deal_damage(self.get_stat('dmg') * divisor, Tags.Arcane, self)
			if self.get_stat('threeseven') and (unit.cur_hp % 10 == 7 or unit.cur_hp % 10 == 3):
				unit.deal_damage(self.get_stat('dmg') * divisor, Tags.Arcane, self)
			if self.get_stat('prime') and not self.isprime(unit.cur_hp):
				#print("Found prime guy")
				unit.deal_damage(self.get_stat('dmg') * divisor, Tags.Arcane, self)
			unit.apply_buff(Silence(),3)
				
		yield


class Overload(Spell):
	def on_init(self):
		self.name = "Overload"
		self.tags = [Tags.Lightning, Tags.Sorcery]
		self.level = 4 ##Aiming for level 4,  high charge count, weaker than chain lightning for huge groups but much stronger on connected groups?
		self.asset = ["TcrsCustomModpack", "Icons", "overload"]

		self.can_target_empty = False
		self.damage = 30
		self.range = 10
		self.max_charges = 15
		self.duration = 2

		self.upgrades['ion'] = (1, 4, "Ionizing", "Also deals arcane damage.")
		self.upgrades['power'] = (1, 3, "Crackle with Power", "If you are part of the connected group, cast lightning bolt on random tiles twice for each unit in the group.")
		self.upgrades['conductive'] = (1, 2, "Superconductivity", "If there are any metallic units in the group, cast conductivity on up to 5 of them before dealing damage.")

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
		count = 5
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
			if not u.is_alive() and self.get_stat('electrify'):
				kills += 1
		#print(kills)
				
		# if self.get_stat('electrify'):
		# 	allies = [a for a in self.caster.level.units if not are_hostile(a, self.caster) and not Tags.Lightning in a.tags and not a.is_player_controlled]
		# 	if allies:
		# 		random.shuffle(allies) ##set size of allies equal to index[kill] to shorten list sometime
		# 		print(allies)
		# 		for i in range(kills):
		# 			print(i)
		# 			allies[i].Anim = None
		# 			BossSpawns.apply_modifier(BossSpawns.Stormtouched, allies[i])
		
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
		self.channel_cast = False
		self.can_target_self = True
		self.tile_index = 0
		self.tiles = []

		self.range = 0
		self.max_charges = 1
		self.max_channel = 20
		self.damage = 20

		self.upgrades['devourmind'] = (1, 2, "Absolute Insanity", "Cast your Devour Mind on every target in the wave.")
		self.upgrades['dedication'] = (1, 3, "Complete Dedication", "If the wave reaches the end of the realm, cast your Heaven's Wrath.")
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
		#print(count)
		#print(len(self.tiles))
		#print(self.tile_index)
		for i in range(count):
			if self.tile_index == len(self.tiles) - 1:
				self.tile_index = 0
				#print("End of stage")
				if self.get_stat('dedication'):
					spell = self.caster.get_or_make_spell(Spells.HeavensWrath)
					self.caster.level.act_cast(self.caster, spell, x, y, pay_costs=False, queue=True)
				break
			t = self.tiles[self.tile_index]
			self.tile_index += 1
			
			if self.get_stat('devourmind'):
				spell = self.caster.get_or_make_spell(Spells.MindDevour)
				#if spell.can_cast(t.x, t.y):
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
		self.name = "Dominoe"
		self.tags = [Tags.Fire, Tags.Sorcery]
		self.level = 3 ##Comparable to death touch and my own absorb. I like this spell but it seems very weak. Its upgrades are cool to compensate.
		self.asset = ["TcrsCustomModpack", "Icons", "dominoe"] ##Moderately ugly, nothing too bad though.
		
		self.range = 1
		self.melee = True
		self.can_target_empty = False
		self.damage = 60
		self.max_charges = 6

		self.upgrades['thunder'] = (1, 2, "Thunderbone's Game", "Summon an electric bone shambler with 16 max hp multiplied by the number of affected units.")
		self.upgrades['bones'] = (1, 2, "Throw the bones", "Each struck unit has a 1/6 chance of summoning a Bone Knight")
		self.upgrades['dominator'] = (1, 3, "Fives and Threes", "If exactly 3 or a multiple of 3 units are targeted, cast your Dominate on 5 viable enemies.")

		##TODO Determine if I should allow horizontal only leaps for when things bunch up in corners. Would greatly improve the utility of the spell across corners.

	def get_description(self):
		return ("Deal [{damage}_fire:fire] to one unit in melee range, and then repeat on one enemy unit adjacent to the target."
				" This repeats any number of times, but never on the same units.").format(**self.fmt_dict())

	def get_extra_examine_tooltips(self):
		elec_shambler = BoneShambler(16)
		BossSpawns.apply_modifier(BossSpawns.Stormtouched, elec_shambler)
		return [self.spell_upgrades[0], elec_shambler, self.spell_upgrades[1], BoneKnight(), self.spell_upgrades[2]]

	def get_impacted_tiles(self, x, y):
		units = []
		u = self.caster.level.get_unit_at(x, y)
		while u != None:
			units.append(u)
			temp_units = []
			for p in self.caster.level.get_adjacent_points(Point(u.x, u.y), filter_walkable=False):
				u = self.caster.level.get_unit_at(p.x, p.y)
				if u != None and u != self.caster and u not in units:
					temp_units.append(u)
			if len(temp_units) != 1:
				u = None
			else:
				u = temp_units[0]

		return units

	def thunder_shambler(self, multiplier):
		unit = BoneShambler(16 * multiplier)
		BossSpawns.apply_modifier(BossSpawns.Stormtouched, unit)
		return unit

	def cast(self, x, y):
		units = self.get_impacted_tiles(x, y)
		for u in units:
			self.caster.level.deal_damage(u.x, u.y, self.get_stat('damage'), Tags.Fire, self)
			if self.get_stat('bones'):
				if random.random() < 0.16:
					unit = BoneKnight()
					self.caster.level.summon(self.caster, unit, Point(u.x, u.y))

		if self.get_stat('dominator') and len(units) % 3 == 0:
			spell = self.caster.get_or_make_spell(Dominate)
			targets = [t for t in self.caster.level.units if are_hostile(t, self.caster) and t.max_hp <= spell.hp_threshold]
			if targets:
				random.shuffle(targets)
				for i in range(min(5, len(targets))):
					for s in self.caster.level.act_cast(self.caster, spell, targets[i].x, targets[i].y, pay_costs=False, queue=False):
						yield
		if self.get_stat('thunder'):
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
		self.description = "Whenever you cast a sorcery spell, copy it once on a random target for each spell you've cast since the buff was applied."
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
		self.range = 0
		self.max_charges = 1
		self.duration = 10

		self.upgrades['lessdmg'] = (1, 3, "Minimal Backlash", "Take damage from 2 of the types instead of all 3. Changes each time the buff is applied.")
		self.upgrades['favour'] = (1, 2, "Favourable Odds", "If an ally is chosen as the target of a copied spell, randomly target another unit. Triggers only once per spell cast.")
		self.upgrades['spendhp'] = (1, 2, "Blood", "The damage from copying spells counts as spending HP for blood spells and skills.")


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
	unit.spells.insert(0, RedRiderBerserkingSpell_Global())
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
		
		self.upgrades['lasting'] = (1, 1, "Cry Havoc", "The Rider's Berserk skill now scales in duration with this spell's bonus duration.")
		self.upgrades['dogs'] = (1, 5, "Dogs of War", "The Rider can now summon hellhounds on a 6 turn cooldown.")
		self.upgrades['faster'] = (1, 1, "Hasted", "The Rider is permanently hasted, taking two turns instead of one.")
		self.upgrades['sustained'] = (1, 2, "Sustaining", "Each turn you channel now adds 3 turns to its lifetime.")

	def get_description(self):
		return ("Summon The Red Rider, a powerful ally that can berserk all enemies on the map for 3 turns, and heals when any enemy takes fire or physical damage.\n"
				"The Rider lasts 1 turn, and each turn you channel this spell adds 1 turn to its lifetime. Can be channeled forever.").format(**self.fmt_dict())

	def get_extra_examine_tooltips(self):
		return [RedRiderMod()] + self.spell_upgrades

	def cast(self, x, y, channel_cast=False):
		if not channel_cast:
			#print("summoned rider")
			unit = RedRiderMod()
			if self.get_stat('lasting'):
				duration = self.get_stat('duration', base=3)
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
				unit.apply_buff(HasteBuff())
			return
		else:
			if not self.unit or not self.unit.is_alive():
				return
			self.unit.turns_to_death += 1
			if self.get_stat('sustained'):
				self.unit.turns_to_death += 2
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
		elif self.get_stat('claws'):
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

		self.upgrades['cold'] = (1, 4, "Cold Shower", "Mogui gain your icicle spell on an 8 turn cooldown. They also multiply on blizzard clouds.")
		self.upgrades['claws'] = (1, 2, "Lightning Claws", "Mogui gain a leaping [Lightning] melee attack with 4 tiles of range. They also multiply on storm clouds.")
		self.upgrades['possess'] = (1, 2, 'Possession', 'When Mogui die or time out, they cast your dominate spell on a nearby target.')

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
		if self.get_stat('leap'):
			leap = LeapAttack(damage=self.get_stat('minion_damage'),range=self.get_stat('minion_range',base=4),damage_type=Tags.Physical,is_leap=True)
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

		self.range = 99
		self.max_charges = 12
	
		self.upgrades['scourge'] = (1, 4, "Scourging Escape", "Cast your scourge spell on [2:num_targets] random unit in line of sight from the starting point.")
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
			for i in range(self.get_stat('num_targets',base=1)):
				if units != []:
					unit = random.choice(units)
					units.remove(unit)
					spell = self.caster.get_or_make_spell(ScourgeSpell)
					self.caster.level.act_cast(self.caster, spell, unit.x, unit.y, pay_costs=False)
				

def Hydra():
	unit = Snake()
	unit.name = "Hydra"
	unit.asset = ["TcrsCustomModpack", "Units", "hydra"]
	unit.max_hp = 54
	unit.spells[0].damage = 18
	unit.buffs.append(SpawnOnDeath(TwoHeadedSnake, 3))
	return unit

class LoadedDice(Buff):
	def __init__(self, roll):
		self.roll = roll
		Buff.__init__(self)
		self.description = "Always roll at least a " + str(roll) + " or higher."

	def on_init(self):
		self.name = "Loaded Dice"
		self.color = Tags.Chaos.color

class ChaosDice(Spell):
	def on_init(self):
		self.name = "Chaotic Ice Dice"
		self.tags = [Tags.Ice, Tags.Chaos, Tags.Sorcery]
		self.asset =  ["TcrsCustomModpack", "Icons", "ice_dice"]
		self.level = 4
		self.max_charges = 6
		self.damage = 10
		self.range = 0
		self.self_target = True
		
		self.upgrades['ice'] = (1, 2, "Pure Ice Dice", "Instead of dealing damage, cast your Iceball or Deathchill spells randomly on the targets.")
		self.upgrades['loaded'] = (1, 2, "Loaded Dice", "Gain a buff that always ensures your next roll is at least 1 value higher than the previous roll. Resets when you roll a '6'.")
		self.upgrades['snake'] = (1, 4, "Snake Eyes", "Roll two times, adding up the total. Each '1' rolled summons a hydra.")
		##Possible upgrade idea - Uses num_targets attribute to increase maximum roll your dice can reach.

	def get_description(self):
		return ("Roll a number between 1 to 6. Deal [{damage}_damage:damage] multiplied by X, to X random enemies where X is the number rolled. \n"
				" The damage is chosen from one of: [Fire], [Lightning], [Ice], and [Physical]. The same enemy is never targeted twice.").format(**self.fmt_dict())

	def get_extra_examine_tooltips(self):
		return [self.spell_upgrades[0], self.spell_upgrades[1], self.spell_upgrades[2], Hydra()]

	def cast(self, x, y):
		roll = random.randint(1,6)
		if self.get_stat('loaded'):
			buff = self.caster.get_buff(LoadedDice)
			if not buff and roll < 6:
				self.caster.apply_buff(LoadedDice(roll))
			elif roll == 6:
				pass  
			else:
				roll = random.randint(buff.roll + 1, 6)
				if roll == 6:
					self.caster.remove_buff(buff)
				else:
					buff.roll = roll
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
				rand_spell = random.choice([Iceball, DeathChill])
				spell = self.caster.get_or_make_spell(rand_spell)
				self.caster.level.act_cast(self.caster, spell, target.x, target.y, pay_costs=False)
				self.caster.level.show_path_effect(self.owner, target, Tags.Ice, minor=True)
			else:
				dtype = random.choice([Tags.Fire, Tags.Lightning, Tags.Physical, Tags.Ice])
				target.deal_damage(self.get_stat('damage') * roll, dtype, self)
				self.owner.level.show_path_effect(self.owner, target, Tags.Chaos, minor=True)
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
			self.tag_bonuses_pct[Tags.Blood]['damage'] = 100

class WraithHunger(Spell):
	def on_init(self):
		self.name = "Wraith's Hunger"
		self.asset = ["TcrsCustomModpack", "Icons", "wraith_hunger"]
		self.tags = [Tags.Arcane, Tags.Sorcery, Tags.Blood]
		self.level = 2
		
		self.hp_cost = 3
		self.damage = 30
		self.range = 5

		self.upgrades['rift'] = (1, 3, "Rift Wraith", "If there is no unit to target, summon a void rift.")
		self.upgrades['drake'] = (1, 6, "Drake Portal", "If you kill the target, cast your Void Drake on its tile.")
		self.upgrades['wrath'] = (1, 2, "Wraith's Wrath", "The debuff also grants blood spells 100% bonus damage.") ##TODO how is this worded in upgrades?
		
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
			elif self.get_stat('drake'):
				spell = self.caster.get_or_make_spell(SummonVoidDrakeSpell)
				self.caster.level.act_cast(self.caster, spell, x, y, pay_costs=False)
		if not unit and self.get_stat('rift'):
			u = VoidSpawner()
			apply_minion_bonuses(self, u)
			self.summon(unit=u, target=Point(x,y))
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
		if self.spell:
			self.owner.level.act_cast(self.owner, self.spell, unit.x, unit.y, pay_costs=False)
		else:
			for t in self.owner.level.get_points_in_rect(unit.x-1, unit.y-1, unit.x+1, unit.y+1):
				self.owner.level.deal_damage(t.x, t.y, self.damage, self.damage_type, self)
		self.level.remove_obj(self)

class Landmines_Minefield(Upgrade):
	def on_init(self):
		self.name = "Recycled Minefield"
		self.level = 2
		self.description = "When a [metallic], [construct], or [glass] unit dies place a landmine on its tile."

		self.global_triggers[EventOnDeath] = self.on_death
	
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

		self.damage = 20
		self.max_charges = 30
		self.range = 99
		self.quick_cast = True
		self.must_target_walkable = True

		self.add_upgrade(Landmines_Minefield())
		self.upgrades['requires_los'] = (-1, 2, "Blindcasting", "Proximity Mine can be cast without line of sight")
		self.upgrades['shrapnel'] = (1, 2, "Shrapnel Mines", "Triggered mines instead use your shrapnel blast spell.")

	def get_description(self):
		return ("Place a mine on target tile. It detonates when a unit moves onto it, dealing [{damage}_physical:physical] in a 3x3 square."
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
		if water_tag in Knowledges:
			self.tags.append(Tags.Water)
		self.level = 5
		self.asset = ["TcrsCustomModpack", "Icons", "sea_serpent_icon"]
		self.max_charges = 2

		self.must_target_empty = True
		self.must_target_walkable = True

		self.minion_health = 75
		self.minion_damage = 14
		self.breath_damage = 10
		self.minion_range = 7

		self.upgrades['rainy'] = (1, 2, "Rain Clouds", "The breath weapon also creates your rain storm clouds on each tile.")
		self.upgrades['gaseous'] = (1, 4, "Poison Clouds", "The breath weapon also creates your poisonous gas clouds on each tile.")
		self.upgrades['abc'] = (1, 4, "ABC Serpent", "The serpent gains 5 max hp, 1 breath damage, and 2 melee damage for each unique letter in the names of spells the caster knows.")

	def get_description(self):
		return ("Summon a Sea Serpent at target square.\n Sea Serpents have [{minion_health}_HP:minion_health], 100 [poison] resistance, and -100 [Ice] and [Lightning] resistances.\n"
				"They have a breath weapon which deals [{breath_damage}_poison:poison] damage and poisons for 5 turns, "
				"and a trampling melee attack which deals [{minion_damage}_physical:physical] damage.").format(**self.fmt_dict())
	
	def get_extra_examine_tooltips(self):
		return [self.wyrm(), self.spell_upgrades[0], self.spell_upgrades[1], self.spell_upgrades[2]]

	def wyrm(self):
		wyrm = SeaSerpent_Unit(self)
		wyrm.max_hp = self.get_stat('minion_health')
		wyrm.spells[0].damage = self.get_stat('breath_damage')
		wyrm.spells[0].range = self.get_stat('minion_range')
		wyrm.spells[1].damage = self.get_stat('minion_damage')
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

def construct_spells():
	spellcon = [MetalShard, CorpseExplosion, FlyWheel, Rockfall, Improvise, Absorb, Haste, BloodOrbSpell, EnchantingCross, Icepath,
				SummonBookwyrm, Exsanguinate, Grotesquify, WordoftheSun, WordofFilth, HolyBeam, Amalgamate, SummonCauldron, OccultBlast,
				RingofFishmen, CallBerserker, ChaosBolt, Machination, Skulldiggery, SummonEyedra, ShieldOrb, PoisonousGas, Hemortar, SummonIcyBeast,
				RainbowSeal, SteelFangs, Leapfrog, KnightlyLeap, SummonChaosBeast, BeckonCowardlyLion, PowerShift, Icebeam, TreeFormSpell,
				AnimateClutter, HP_X_Damage, Overload, UtterDestruction, DominoeAttack, UnstableSpellStorm, Cloudwalk, TheSecondSeal,
				RainDemonMogui, MitreMovement, ChaosDice, WraithHunger, Landmines, SeaSerpent
				]
	print("Added " + str(len(spellcon)) + " spells")
	for s in spellcon:
		Spells.all_player_spell_constructors.append(s)