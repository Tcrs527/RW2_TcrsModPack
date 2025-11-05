from threading import main_thread
import Spells
import BossSpawns
import copy
from Level import *
from Monsters import *
from CommonContent import *

print("General Content Loaded")

##Testing new tag changes, will require changing reverse_tag_key() in RiftWizard2.py TODO

##--------------------Tag Things--------------------

def TagConvertor():
	tagdict = {	Tags.Living:Tags.Nature,
				Tags.Undead:Tags.Dark,
				Tags.Demon:Tags.Dark,
				Tags.Construct:Tags.Metallic,
				Tags.Glass:Tags.Arcane,
				Tags.Elemental:Tags.Conjuration }
	return tagdict

def TagToDmgTagConvertor():
	tagdict = {	Tags.Fire:Tags.Fire,
				Tags.Ice:Tags.Ice,
				Tags.Lightning:Tags.Lightning,
				Tags.Arcane:Tags.Arcane,
				Tags.Dark:Tags.Dark,
				Tags.Holy:Tags.Holy,
				Tags.Living:Tags.Poison,
	    		Tags.Slime:Tags.Poison,
				Tags.Nature:Tags.Poison,
				Tags.Spider:Tags.Poison,
				Tags.Undead:Tags.Dark,
				Tags.Demon:Tags.Dark,
				Tags.Blood:Tags.Dark,
				Tags.Construct:Tags.Physical,
				Tags.Metallic:Tags.Physical,
				Tags.Glass:Tags.Arcane
				}
	return tagdict
	
def ScrollConvertor():
	tagdict = { Tags.Fire:[Spells.FireballSpell,LivingFireScroll_Custom],
				Tags.Ice:[Spells.Icicle,LivingIceScroll],
				Tags.Lightning:[Spells.LightningBoltSpell,LivingLightningScroll_Custom],
				Tags.Arcane:[Spells.MagicMissile,LivingArcaneScroll],
				Tags.Dark:[Spells.DeathBolt,LivingDarknessScroll],
				Tags.Nature:[Spells.PoisonSting,LivingNatureScroll],
				Tags.Holy:[Spells.HolyBlast,LivingHolyScroll],
				Tags.Blood:[Spells.BloodTapSpell,LivingBloodScroll]}
	return tagdict

def ModConvertor():
	tagdict = {	Tags.Fire:BossSpawns.Flametouched,
				Tags.Ice:BossSpawns.Icy,
				Tags.Arcane:BossSpawns.Faetouched,
				Tags.Lightning:BossSpawns.Stormtouched,
				Tags.Chaos:BossSpawns.Chaostouched,
				Tags.Metallic:BossSpawns.Metallic,
				Tags.Undead:BossSpawns.Ghostly,
				Tags.Dark:BossSpawns.Lich,
				Tags.Nature:BossSpawns.Claytouched,
				Tags.Living:BossSpawns.Trollblooded,
				Tags.Holy:BossSpawns.Immortal}
	return tagdict

class LivingScrollSuicide(Buff):
	def on_init(self):
		self.buff_type = BUFF_TYPE_PASSIVE
		self.name = "Fragile"
		self.description = "Dies when it casts any spell."
		self.color = Tags.Physical.color
		self.owner_triggers[EventOnSpellCast] = self.on_cast
		
	def on_cast(self, evt):
		self.owner.kill()

def LivingScrollBase(): ##TODO make all living scrolls based off of this
	unit = Unit()
	unit.name = "DEBUG Living Scroll"
	unit.flying = True
	unit.max_hp = 5
	unit.resists[Tags.Arcane] = 100
	unit.tags = [Tags.Arcane, Tags.Construct]
	unit.buffs.append(LivingScrollSuicide())
	return unit

def LivingFireScroll_Custom():
	unit = LivingScrollBase()
	unit.name = "Living Scroll of Fire"
	unit.asset_name = "living_fireball_scroll" ##TODO Change assets to my style of scrolls
	unit.resists[Tags.Fire] = 100
	unit.tags.append(Tags.Fire)

	return unit

def LivingLightningScroll_Custom():
	unit = LivingScrollBase()
	unit.name = "Living Scroll of Lightning"
	unit.asset_name = "living_lightning_scroll" #TODO change assets once again to my scrolls
	unit.resists[Tags.Lightning] = 100
	unit.tags.append(Tags.Lightning)

	return unit

def LivingDarknessScroll():

	unit = LivingScrollBase()
	unit.name = "Living Scroll of Darkness"
	unit.asset =  ["TcrsCustomModpack", "Units", "living_scroll_darkness3"]
	unit.resists[Tags.Dark] = 100
	unit.tags.append(Tags.Dark)

	return unit

def LivingHolyScroll():

	unit = LivingScrollBase()
	unit.name = "Living Scroll of Holiness"
	unit.asset =  ["TcrsCustomModpack", "Units", "living_scroll_holy2"]
	unit.resists[Tags.Holy] = 100
	unit.tags.append(Tags.Holy)

	return unit

def LivingIceScroll():

	unit = LivingScrollBase()
	unit.name = "Living Scroll of Ice"
	unit.asset =  ["TcrsCustomModpack", "Units", "living_scroll_ice2"]
	unit.resists[Tags.Ice] = 100
	unit.tags.append(Tags.Ice)

	return unit

def LivingArcaneScroll():

	unit = LivingScrollBase()
	unit.name = "Living Scroll of Arcane"
	unit.asset =  ["TcrsCustomModpack", "Units", "living_scroll_arcane2"]

	return unit

def LivingNatureScroll():

	unit = LivingScrollBase()
	unit.name = "Living Scroll of Nature"
	unit.asset =  ["TcrsCustomModpack", "Units", "living_scroll_nature2"]
	unit.tags.append(Tags.Nature)

	return unit

def LivingMetalScroll():

	unit = LivingScrollBase()
	unit.name = "Living Scroll of Metal"
	unit.asset =  ["TcrsCustomModpack", "Units", "living_scroll_metallic"]
	unit.tags.append(Tags.Metallic)

	return unit

def LivingChaosScroll():
	unit = LivingScrollBase()
	unit.name = "Living Scroll of Chaos"
	unit.asset =  ["TcrsCustomModpack", "Units", "living_scroll_chaos"]
	unit.resists[Tags.Fire] = 75
	unit.resists[Tags.Lightning] = 75
	unit.resists[Tags.Physical] = 75
	unit.tags.append(Tags.Chaos)

	return unit

def LivingBloodScroll():
	unit = LivingScrollBase()
	unit.name = "Living Scroll of Blood"
	unit.asset =  ["TcrsCustomModpack", "Units", "living_scroll_blood"]
	unit.resists[Tags.Dark] = 75
	unit.tags.append(Tags.Blood)
	
	return unit



class SlimeCantripEducation(Spell):
	def on_init(self):
		self.name = "Slime Education"
		self.description = "Grants a different slime within 8 tiles a random level 1 sorcery, as long as it does not already know a sorcery."
		self.range = 0
		self.cool_down = 2
		self.radius = 8
		self.cantrips = None
		
	def get_nearby_slimes(self, x, y):
		slimes = [u for u in self.caster.level.get_units_in_ball(Point(x, y), self.get_stat('radius')) if not are_hostile(u, self.caster) and Tags.Slime in u.tags and u != self.caster]
		if slimes == []:
			return None
		uneducated = []
		for u in slimes:
			cantrip = False
			for s in u.spells:
				if Tags.Sorcery in s.tags:
					cantrip = True
			if cantrip == False:
				uneducated.append(u)
		if uneducated == []:
			return
		return uneducated

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
		self.caster.level.show_effect(slime.x, slime.y, Tags.Arcane)
		
		if self.cantrips == None: ##Calculate this per spell once, shouldn't be changing mid realm, even during amnesiac or whatever
			spells = [s for s in Spells.all_player_spell_constructors]
			cantrips = []
			for c in spells:
				if c().level == 1 and Tags.Sorcery in c().tags:
					cantrips.append(c)
			self.cantrips = cantrips

		spell = random.choice(self.cantrips)()
		spell.statholder = slime
		spell.caster = slime
		spell.owner = slime
		spell.description = " "
		
		slime.spells.insert(0, spell)
		yield

def LearnedSlime():
	unit = Unit()
	unit.name = "Slime Scholar"
	unit.max_hp = 10
	unit.tags = [Tags.Slime, Tags.Arcane]
	unit.asset = ["TcrsCustomModpack", "Units", "slime_scholar"]

	unit.spells.append(SlimeCantripEducation())
	unit.buffs.append(SlimeBuff(spawner=LearnedSlime))

	unit.resists[Tags.Poison] = 100
	return unit



def get_skill_charges(unit, tag):
	base_charges = unit.tag_bonuses[tag]['max_charges']
	multiplier = 1 + (unit.tag_bonuses_pct[tag]['max_charges'] / 100)
	return base_charges * multiplier

##--------------------Tiles--------------------

class PoisonCloud_Old(Cloud): ##In case I want to keep the old method and remove the new form

	def __init__(self, owner, damage=6):
		Cloud.__init__(self)
		self.owner = owner
		self.duration = 6
		self.damage = damage
		self.color = Tags.Poison.color
		self.name = "Poison Cloud"
		self.description = "Every turn, deals %d poison damage to any creature standing within, then debuffs them." % self.damage
		self.asset_name = 'poison_cloud'
		self.buff = None
		self.buff_turns = 3

	def on_advance(self):
		unit = self.level.get_unit_at(self.x, self.y)
		if unit and unit.resists[Tags.Poison] < 100:
			buff = copy.deepcopy(self.buff)
			unit.apply_buff(Poison(), self.buff_turns)
			if buff != None:
				unit.apply_buff(buff, self.buff_turns)
		self.level.deal_damage(self.x, self.y, self.damage, Tags.Poison, self)

class PoisonCloud(Cloud):

	def __init__(self, owner, damage=6):
		Cloud.__init__(self)
		self.owner = owner
		self.duration = 6
		self.damage = damage
		self.color = Tags.Poison.color
		self.name = "Poison Cloud"
		self.description = "Every turn, deals %d poison damage to any creature standing within, then debuffs them." % self.damage
		self.asset = ['TcrsCustomModpack', 'Tiles' ,'poison_cloud']
		self.buff = None
		self.buff_turns = 3

	def on_advance(self):
		unit = self.level.get_unit_at(self.x, self.y)
		if unit and unit.resists[Tags.Poison] < 100:
			unit.apply_buff(Poison(), self.buff_turns)
			if self.buff != None:
				unit.apply_buff(self.buff, self.buff_turns)
				self.buff = None
		self.level.deal_damage(self.x, self.y, self.damage, Tags.Poison, self)

class Sandstorm(Cloud):
	def __init__(self, owner, damage=2, duration=5, buff_duration=1):
		Cloud.__init__(self)
		self.damage = damage
		self.owner = owner
		self.source = None
		self.duration = duration
		self.buff_duration = buff_duration
		self.color = Tags.Nature.color
		self.name = "Sandstorm"
		self.description = "Every turn, deals %d physical damage to any creature standing within, then blinds them." % self.damage
		self.asset = ['TcrsCustomModpack', 'Tiles' ,'sandstorm_3']

	def on_advance(self):
		unit = self.level.get_unit_at(self.x, self.y)
		if unit and unit.resists[Tags.Physical] < 100:
			unit.apply_buff(BlindBuff(), self.buff_duration)
		self.level.deal_damage(self.x, self.y, self.damage, Tags.Physical, self.source)

class Hole(Cloud):

	def __init__(self):
		Cloud.__init__(self)
		self.name = "Hole"
		self.color = Color(210, 210, 210)
		self.description = "Any non-flying unit entering the web is stunned for 1 turn.  This destroys the hole."
		self.duration = 12
		
		self.asset_name = ["TcrsCustomModpack", "Tiles", "hole"] ##TODO Clouds are dumb
		#self.asset_name = "hole"

	def on_unit_enter(self, unit):
		if unit.flying != True:
			unit.apply_buff(Stun(), 2)
			self.kill()

##--------------------Buffs--------------------

class Fear(Buff): ##Migrate all fear effects over to Dylan's Fear

	def on_init(self):
		self.buff_type = BUFF_TYPE_CURSE
		self.stack_type	= STACK_NONE
		self.name = "Feared"
		self.color = Tags.Dark.color
		#self.asset = ['status', 'stun']
		self.description = "Run away from enemies."
		
		##Make constructs immune?

	def on_attempt_apply(self, owner):
		if owner.gets_clarity and owner.has_buff(Fear):
			return False
		return True
	
	def on_unapplied(self):
		self.owner.is_coward = False
		if self.owner.gets_clarity:
			self.owner.apply_buff(StunImmune(), 1)

	def on_applied(self, owner):
		if owner.has_buff(StunImmune):
			return ABORT_BUFF_APPLY
		self.owner.is_coward = True

class Disoriented(Buff):
	def on_init(self):
		self.buff_type = BUFF_TYPE_CURSE
		self.stack_type	= STACK_NONE
		self.name = "Disoriented"
		self.color = Tags.Construct.color
		#self.asset = ['status', 'stun']
		self.description = "Moves randomly"
		self.owner_triggers[EventOnMoved] = self.on_move
		self.moved = False
		
	def on_move(self, evt):
		if self.moved:
			self.moved = False
			return
		else:
			self.moved = True
		points = self.owner.level.get_points_in_rect(self.owner.x - 1, self.owner.y - 1, self.owner.x + 1, self.owner.y + 1)
		available_p = [p for p in points if self.owner.level.can_move(self.owner, p.x, p.y, teleport=False)]
		if available_p == []:
			return
		p = random.choice(available_p)
		self.owner.level.act_move(self.owner, p.x, p.y, teleport=False)
		self.owner.apply_buff(Stun(),1)


class Sleep(Stun):
	def on_init(self):
		self.buff_type = BUFF_TYPE_CURSE
		self.stack_type	= STACK_NONE
		self.name = "Asleep"
		self.color = Tags.Arcane.color
		#self.asset = ['status', 'stun']
		self.description = "Stunned until you take damage."
		self.owner_triggers[EventOnDamaged] = self.on_damage
		
	def on_attempt_apply(self, owner):
		if owner.gets_clarity and owner.has_buff(Sleep):
			return False
		return True

	def on_applied(self, owner):
		return Stun.on_applied(self, owner)

	def on_damage(self, evt):
		self.owner.remove_buff(self)

	def on_unapplied(self):
		Stun.on_unapplied(self)

class HasteBuff(Buff):
	def __init__(self):
		Buff.__init__(self)

	def on_init(self):
		self.name = "Haste"
		self.buff_type = BUFF_TYPE_BLESS
		self.color = Tags.Lightning.color
		self.stack_type = STACK_REPLACE
		self.asset = ["TcrsCustomModpack", "Icons", "buff_haste"]
	
	def on_advance(self):
		if self.owner.is_alive():
			self.owner.advance()

##--------------------Units--------------------

def Hydra():
	snek = Unit()
	snek.name = "Hydra"
	snek.asset =  ["TcrsCustomModpack", "Units", "hydra"]
	snek.max_hp = 72
	snek.spells.append(SimpleMeleeAttack(24, buff=Poison, buff_duration=10))
	snek.resists[Tags.Ice] = -50
	snek.tags = [Tags.Living, Tags.Nature]

	snek.buffs.append(SpawnOnDeath(TwoHeadedSnake, 4))
	return snek

def HolyGhost():
	spirit = Unit()
	spirit.name = "Spirit"
	spirit.asset_name = "holy_ghost"
	spirit.max_hp = 4
	spirit.spells.append(SimpleRangedAttack(damage=2, damage_type=Tags.Holy, range=3))
	spirit.tags = [Tags.Holy, Tags.Undead]
	spirit.buffs.append(TeleportyBuff())
	spirit.resists[Tags.Holy] = 100
	spirit.resists[Tags.Dark] = -100
	spirit.resists[Tags.Physical] = 100
	spirit.flying = True
	return spirit

def DeathGhost():
	death = Ghost()
	death.name = "Death Ghost"
	death.asset_name = "death_ghost"
	death.spells.append(SimpleRangedAttack(damage=2, range=3, damage_type=Tags.Dark))
	death.resists[Tags.Dark] = 100
	return death

class StealCantrip(Spell):
	def on_init(self):
		self.name = "Copy Cantrip"
		self.description = "Copies two of the Wizard's cantrips, or chooses random ones."
		self.range = 0
		self.cool_down = 50
		
	def cast(self, x, y):
		wizard = [u for u in self.caster.level.units if u.name == "Wizard"]
		wizard = wizard[0]
		cantrips = []
		for s in wizard.spells:
			if s.level == 1 and Tags.Sorcery in s.tags:
				spell = copy.deepcopy(s)
				cantrips.append(spell)
		length = len(cantrips)
		if length >= 2:
			length = 2
			cantrips = cantrips[:2]
		for i in range(2 - length):
			cantrips.append(random.choice([Spells.FireballSpell(), Spells.Icicle(), Spells.LightningBoltSpell(), Spells.PoisonSting(),
							Spells.MagicMissile(), Spells.DeathBolt()]))
		for spell in cantrips:
			spell.max_charges = 0
			spell.cur_charges = 0
			spell.cool_down = 1
			spell.statholder = wizard
			spell.caster = self.caster
			spell.owner = self.caster
			self.caster.spells.insert(0, spell)
		yield

def CantripBrocade():
	unit = Unit()
	unit.name = "Cantripy Brocade"
	unit.max_hp = 1
	unit.shields = 5
	unit.tags = [Tags.Arcane, Tags.Construct, Tags.Sorcery]
	unit.description = "A magic carpet that casts random cantrips."
	unit.spells.append(StealCantrip())
	return unit
