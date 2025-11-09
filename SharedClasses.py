from pydoc import describe
from threading import main_thread
import Spells
import BossSpawns
import copy
from Level import *
from Monsters import *
from Variants import StarfireSnakeGiant, ChaosSnakeGiant, SnakeGiant
from CommonContent import *

print("General Content Loaded")

##Testing new tag changes, will require changing reverse_tag_key() in RiftWizard2.py TODO

water_tag = Tag("Water", Color(14,14,250)) ##Purely for cross-mod compatibility

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
				Tags.Demon:BossSpawns.Chaostouched,
				Tags.Metallic:BossSpawns.Metallic,
				Tags.Construct:BossSpawns.Metallic,
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
	unit.asset =  ["TcrsCustomModpack", "Units-Variant", "living_scroll_darkness3"]
	unit.resists[Tags.Dark] = 100
	unit.tags.append(Tags.Dark)

	return unit

def LivingHolyScroll():

	unit = LivingScrollBase()
	unit.name = "Living Scroll of Holiness"
	unit.asset =  ["TcrsCustomModpack", "Units-Variant", "living_scroll_holy2"]
	unit.resists[Tags.Holy] = 100
	unit.tags.append(Tags.Holy)

	return unit

def LivingIceScroll():

	unit = LivingScrollBase()
	unit.name = "Living Scroll of Ice"
	unit.asset =  ["TcrsCustomModpack", "Units-Variant", "living_scroll_ice2"]
	unit.resists[Tags.Ice] = 100
	unit.tags.append(Tags.Ice)

	return unit

def LivingArcaneScroll():

	unit = LivingScrollBase()
	unit.name = "Living Scroll of Arcane"
	unit.asset =  ["TcrsCustomModpack", "Units-Variant", "living_scroll_arcane2"]

	return unit

def LivingNatureScroll():

	unit = LivingScrollBase()
	unit.name = "Living Scroll of Nature"
	unit.asset =  ["TcrsCustomModpack", "Units-Variant", "living_scroll_nature2"]
	unit.tags.append(Tags.Nature)

	return unit

def LivingMetalScroll():

	unit = LivingScrollBase()
	unit.name = "Living Scroll of Metal"
	unit.asset =  ["TcrsCustomModpack", "Units-Variant", "living_scroll_metallic"]
	unit.tags.append(Tags.Metallic)

	return unit

def LivingChaosScroll():
	unit = LivingScrollBase()
	unit.name = "Living Scroll of Chaos"
	unit.asset =  ["TcrsCustomModpack", "Units-Variant", "living_scroll_chaos"]
	unit.resists[Tags.Fire] = 75
	unit.resists[Tags.Lightning] = 75
	unit.resists[Tags.Physical] = 75
	unit.tags.append(Tags.Chaos)

	return unit

def LivingBloodScroll():
	unit = LivingScrollBase()
	unit.name = "Living Scroll of Blood"
	unit.asset =  ["TcrsCustomModpack", "Units-Variant", "living_scroll_blood"]
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

class Fear_OLD(Buff): ##Migrate all fear effects over to Dylan's Fear - Has been fully deprecated

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
		self.description = "Has 2 actions per turn."
		self.buff_type = BUFF_TYPE_BLESS
		self.color = Tags.Lightning.color
		self.stack_type = STACK_REPLACE
		self.asset = ["TcrsCustomModpack", "Icons", "buff_haste"]
	
	def on_advance(self):
		if self.owner.is_alive():
			self.owner.advance()

##--------------------Units--------------------

def Hydra():
	unit = Unit()
	unit.name = "Hydra"
	unit.asset =  ["TcrsCustomModpack", "Units", "hydra"]
	unit.max_hp = 72
	unit.spells.append(SimpleMeleeAttack(3, attacks=8, buff=Poison, buff_duration=24))
	unit.resists[Tags.Ice] = -50
	unit.tags = [Tags.Living, Tags.Nature]

	unit.buffs.append(SpawnOnDeath(TwoHeadedSnake, 4))
	return unit


def Tachi():
	unit = DancingBlade()
	unit.name = "Tachi"
	unit.asset = ["TcrsCustomModpack", "Units", "spectral_blade_amaterasu"]
	unit.max_hp = 45
	unit.shields = 2
	unit.spells[0].name = "Dancing Blade"
	unit.spells[0].damage = 12
	unit.spells[0].range = 6
	unit.buffs.append(HasteBuff())
	return unit


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
		self.cool_down = 99
		
	def cast(self, x, y):
		wizard = self.caster.level.player_unit
		your_cantrips = []
		cantrips = []
		for s in wizard.spells:
			if s.level == 1 and Tags.Sorcery in s.tags:
				your_cantrips.append(s)

		if len(your_cantrips) >= 2:
			cantrip_spells = your_cantrips[:2]
			for i in range(2):
				cantrips.append(type(cantrip_spells[i]))

		elif len(your_cantrips) == 1:
			cantrips.append(type(your_cantrips[0]))
			cantrip_spells = [s for s in Spells.all_player_spell_constructors if Tags.Sorcery in s().tags and s().level == 1]
			random.shuffle(cantrip_spells)
			cantrips.append(cantrip_spells[0])
		else:
			cantrip_spells = [s for s in Spells.all_player_spell_constructors if Tags.Sorcery in s().tags and s().level == 1]
			random.shuffle(cantrip_spells)
			cantrips = cantrip_spells[:2]
			
		print(cantrips)
		for s in cantrips:
			spell = grant_minion_spell(s, self.owner, master=wizard, cool_down=2)
			spell.description = " "
		yield

def CantripBrocade():
	unit = Unit()
	unit.name = "Cantrip Brocade"
	unit.asset = ["TcrsCustomModpack", "Units", "cantrip_brocade"]
	unit.max_hp = 16
	unit.shields = 6
	unit.tags = [Tags.Arcane, Tags.Construct, Tags.Sorcery]
	unit.description = "A magic carpet that casts random cantrips."
	unit.spells.append(StealCantrip())
	return unit


def Fishman():
	unit = Unit()
	unit.max_hp = 25

	unit.name = "Fishman"
	unit.asset = ["TcrsCustomModpack", "Units-Variant", "fishman"] #Credit to K.Hoops' Stonefish sprite as the general fish design in RW
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
	unit.asset = ["TcrsCustomModpack", "Units-Variant", "fishmancat"] #Catfish have the same colour scheme as accursed cats

	unit.spells[0] = (SimpleMeleeAttack(damage=8,damage_type=Tags.Dark))
	unit.buffs.append(ReincarnationBuff(1))
	unit.resists[Tags.Dark] = 100
	unit.resists[Tags.Holy] = -100

	return unit

def FishmanArcher():
	unit = Fishman()
	unit.name = "Archerfish Man"
	unit.asset = ["TcrsCustomModpack", "Units-Variant", "fishmanarcher"]
	unit.tags.append(Tags.Ice)

	unit.spells[0] = (SimpleRangedAttack(damage=8, damage_type=Tags.Ice, cool_down=2, range=10,proj_name="kobold_arrow_long"))
	unit.resists[Tags.Ice] = 50

	return unit

def FishmanLion():
	unit = Fishman()
	unit.name = "Lionfish Man"
	unit.asset = ["TcrsCustomModpack", "Units-Variant", "fishmanlion"]
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
		if self.parent_spell == None:
			unit = Fishman()
			self.idol_spell.owner.level.summon(self.idol_spell.owner, unit, target=self.owner, team=self.idol_spell.owner.team)
		else:
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

def IdolDepths(spell=None):
	idol = Idol()
	idol.name = "Idol of the Depths"
	idol.asset = ["TcrsCustomModpack", "Units", "idol_of_depths"]
	idol.spells.append(Fishification(spell))
	idol.resists[Tags.Dark] = 100
	return idol


def AmalgamateUnit(hp=127, spell=None):
	unit = Unit()
	unit.name = "Amalgamation"
	unit.max_hp = hp
	if unit.max_hp <= 24:  #Credit to K.Hoops for the flesh fiend sprite. Its mouth serves as the basis for all amalgams.
		unit.asset = ["TcrsCustomModpack", "Units-Variant", "amalgamate_small"]
	elif unit.max_hp <= 120:
		unit.asset = ["TcrsCustomModpack", "Units-Variant", "amalgamate_med"]
	else:
		unit.asset = ["TcrsCustomModpack", "Units-Variant", "amalgamate_large"]
	unit.buffs.append(RegenBuff(unit.max_hp//10))
	
	unit.tags = [Tags.Living, Tags.Construct]
	if spell == None:
		bonus_tag1 = random.choice([Tags.Fire, Tags.Ice, Tags.Lightning, Tags.Arcane, Tags.Dark, Tags.Poison])
		unit.tags.append(bonus_tag1)
		unit.spells.append(SimpleRangedAttack(damage=15,damage_type=bonus_tag1,range=3,cool_down=1))
		bonus_tag2 = random.choice([Tags.Fire, Tags.Ice, Tags.Lightning, Tags.Arcane, Tags.Dark, Tags.Physical])
		unit.spells.append(SimpleMeleeAttack(damage=15,damage_type=bonus_tag2,attacks=2))
		bonus_tag3 = random.choice([Tags.Metallic, Tags.Demon, Tags.Glass, Tags.Slime])
		unit.tags.append(bonus_tag3)

		unit.resists[Tags.Physical] = random.choice([-25, -50, -75, -100])
		unit.resists[Tags.Poison] = random.choice([-25, -50, -75, -100])
		unit.resists[Tags.Fire] = random.choice([-25, -50, -75, -100])
		unit.resists[Tags.Holy] = random.choice([-25, -50, -75, -100])

	return unit


class ChaosBeastMaxHp(Buff):
	def on_init(self):
		self.stack_type = STACK_NONE
		self.buff_type = BUFF_TYPE_PASSIVE
		self.color = Tags.Heal.color
		self.owner_triggers[EventOnDamaged] = self.on_dmg

	def on_dmg(self, evt):
		if Tags.Fire == evt.damage_type or Tags.Lightning == evt.damage_type or Tags.Physical == evt.damage_type:
			self.owner.max_hp += evt.damage

	def get_tooltip(self):
		return "Gains max hp equal to the damage taken, when it takes fire, lightning, or physical damage. This does not cause healing."

class ChaosBeastSpawner(Buff):
	def __init__(self, spell=None):
		self.spell = spell
		Buff.__init__(self)
		
	def on_init(self):
		self.name = "Snakeball"
		self.stack_type = STACK_NONE
		self.buff_type = BUFF_TYPE_PASSIVE
		self.color = Tags.Chaos.color
		self.owner_triggers[EventOnDeath] = self.on_death
		
	def get_tooltip(self):
		return "Summons snakes upon death, increasing by 1 for every 9 max hp."

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
	unit.resists[Tags.Ice] = -50
	
	unit.buffs.append(ChaosBeastSpawner(s))
	unit.buffs.append(ChaosBeastMaxHp())
	return unit


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

	unit.spells.append(SeaWyrmBreath(s))
	unit.spells.append(SimpleMeleeAttack(14, trample=True))

	unit.tags = [Tags.Nature, Tags.Dragon, Tags.Living]
	if water_tag in Knowledges:
		unit.tags.append(Tags.Water)

	unit.resists[Tags.Poison] = 100
	unit.resists[Tags.Lightning] = -100
	unit.resists[Tags.Ice] = -100
	return unit


def SandElemental():
	unit = Unit()
	unit.name = "Sand Elemental"
	unit.asset = ["TcrsCustomModpack", "Units", "sand_elemental"]
	unit.max_hp = 40

	unit.spells.append(SimpleMeleeAttack(damage=8, buff=BlindBuff, buff_duration=2))
	unit.spells.append(LeapAttack(damage=8, range=4))

	unit.flying = True
	unit.tags = [Tags.Elemental, Tags.Nature]
	unit.resists[Tags.Poison] = 100
	unit.resists[Tags.Physical] = 75

	return unit


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
	
	melee_attack = SimpleMeleeAttack(damage=2, damage_type=Tags.Dark, drain=True,attacks=max(3,unit.max_hp//20))
	melee_attack.name="Biting Flies"
	melee_attack.quick_cast = True
	unit.spells.append(melee_attack)
	#proj_name = [["TcrsCustomModpack", "Misc", "swarm_shot"]] ##TODO figure out ##figured out, incorporate sometime
	unit.spells.append(SimpleRangedAttack(name="Swarmshot", damage=max(5,unit.max_hp//10), damage_type=Tags.Physical, range=5,proj_name="petrification"))
	unit.buffs.append(RegenBuff(6))
	unit.buffs.append(ReformingSpawn(FlyCloud,19)) ##Sets number in buff
	return unit



class GalvanizationTransformation(Buff):
	def __init__(self, spell=None):
		self.spell = spell
		Buff.__init__(self)
		
	def on_init(self):
		self.buff_type = BUFF_TYPE_BLESS
		self.stack_type	= STACK_TYPE_TRANSFORM
		self.transform_asset = ["TcrsCustomModpack", "Units", "galvanni_beast_active"]
		self.name = "Galvanized"
		self.color = Tags.Lightning.color
		self.description = "Remains awake for only a limited amount of time."
		self.devour = None

	def on_applied(self, owner):
		self.owner.stationary = False
		
		devour = SimpleMeleeAttack(damage=30,damage_type=Tags.Physical, buff=FearBuff, buff_duration=2)
		devour.caster = self.owner
		devour.owner = self.owner
		if self.spell != None:
			damage = self.spell.get_stat('minion_damage')
			devour.damage = damage
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
		if self.spell == None:
			self.owner.apply_buff(GalvanizationTriggers(self.spell))

class GalvanizationTriggers(Buff): ##A bit of a nightmare class trying to cover what really should be 2 separate buffs for spell vs non-spell galvanization
	def __init__(self, spell=None):
		self.spell = spell
		Buff.__init__(self)
		
	def on_init(self):
		self.buff_type = BUFF_TYPE_PASSIVE
		self.stack_type	= STACK_NONE
		self.count = 20
		self.blood_remainder = 0
		self.color = Tags.Physical.color
		self.owner_triggers[EventOnDamaged] = self.on_dmg
		if self.spell != None:
			self.description = ("Awakens for %d turns when it takes [lightning] damage or any HP is spent on [blood] spells.\nHeals 100%% of [lightning] damage taken.") % self.spell.get_stat('duration')
			self.global_triggers[EventOnSpendHP] = self.spend_hp
		else:
			self.description = "Awakens after 20 turns, for 15 turns. Any [lightning] damage causes it to awaken instantly."

	def get_tooltip(self):
		return self.description

	def on_advance(self):
		if self.spell == None:
			self.count -= 1
			self.description = "Awakens after " + str(self.count) + " turns, for 15 turns. Any [lightning] damage causes it to awaken instantly."
			if self.count <= 0:
				buff = GalvanizationTransformation()
				self.owner.apply_buff(buff,15)
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
			if self.spell == None:
				buff = GalvanizationTransformation()
				self.owner.apply_buff(buff,15)
				self.owner.remove_buff(self)
			else:
				self.owner.level.deal_damage(self.owner.x, self.owner.y, -evt.damage, Tags.Heal, self)
				self.transformation(self.spell.get_stat('duration'))
		elif evt.damage_type == Tags.Fire and self.spell.get_stat('furnace'):
			self.transformation(self.spell.get_stat('duration'))

def GalvanizedHorror(spell=None):
	unit = Unit()
	unit.max_hp = 320
	unit.name = "Galvanized Horror"
	unit.asset = ["TcrsCustomModpack", "Units", "galvanni_beast_dorm"]
	
	unit.tags = [Tags.Blood, Tags.Lightning]
	unit.resists[Tags.Dark] = 50
	unit.resists[Tags.Physical] = 50
	unit.resists[Tags.Holy] = -50
	unit.resists[Tags.Ice] = -50
	unit.resists[Tags.Arcane] - 50
	unit.stationary = True
	unit.buffs.append(Thorns(12,Tags.Lightning))
	unit.buffs.append(GalvanizationTriggers(spell))
	return unit


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
	unit.resists[Tags.Dark] = -50

	return unit


def IceShambler(HP=64):
	unit = Unit()
	unit.max_hp = HP
	unit.tags = [Tags.Elemental, Tags.Ice, Tags.Undead]
	unit.resists[Tags.Ice] = 100
	unit.resists[Tags.Fire] = -100

	if HP >= 64:
		unit.name = "Iceberg Shambler"
		unit.asset = ["TcrsCustomModpack", "Units-Variant", "ice_shambler_large"]
		unit.spells.append(SimpleRangedAttack(damage=16, range=4, damage_type=Tags.Ice, buff=FrozenBuff, buff_duration=1))
	elif HP >= 8:
		unit.name = "Ice Shambler"
		unit.asset = ["TcrsCustomModpack", "Units-Variant", "ice_shambler_med"]
		unit.spells.append(SimpleRangedAttack(damage=8, range=3, damage_type=Tags.Ice, buff=FrozenBuff, buff_duration=1))
	else:
		unit.name = "Icicle Shambler"
		unit.asset = ["TcrsCustomModpack", "Units-Variant", "ice_shambler_small"]
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



class SlimePriestGrowth(SlimeBuff):
	def __init__(self, spell=None):
		self.spell = spell
		Buff.__init__(self)
		self.description = "50%% chance to gain 7 hp and 7 max hp per turn.  Upon reaching double max HP, consume half of max hp to transform and stop gaining max hp."
		self.name = "Slime Growth"
		self.color = Tags.Slime.color
		self.spawner = GreenSlime
		self.spawner_name = 'slimes'
		self.growth_chance = 0.5

	def on_applied(self, owner):
		self.start_hp = self.owner.max_hp
		self.to_split = self.start_hp * 2
		self.growth = self.start_hp // 4
		self.description = "50%% chance to gain %d hp and max hp per turn.  Upon reaching %d HP, consume half of max hp to transform and stop gaining max hp." % (self.growth, self.to_split)
		
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
			if self.spell == None:
				duration = 20
			else:
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
		self.resists[Tags.Physical] = 50
		self.resists[Tags.Arcane] = 50
		self.transform_asset = ["TcrsCustomModpack", "Units", "slimepriest_monster"]
		self.description = "Transform into a Slime"
		if self.spell == None:
			slimespew = SimpleRangedAttack(name="Slimy Spew", damage=10, damage_type=Tags.Poison, radius=1, range=3 )
		else:
			slimespew = SimpleRangedAttack(name="Slimy Spew",damage=self.spell.get_stat('minion_damage'), damage_type=Tags.Poison, radius=1, range=self.spell.get_stat('minion_range') )
		self.spells = [slimespew]

def SlimePriest(spell=None):
	unit = Unit()
	unit.name = "Goo Priest"
	unit.asset = ["TcrsCustomModpack", "Units", "slimepriest"]
	unit.tags = [Tags.Living, Tags.Holy, Tags.Slime]
	unit.max_hp = 36
	unit.resists[Tags.Poison] = 100
	unit.resists[Tags.Holy] = 100
	unit.resists[Tags.Physical] = - 50
	unit.resists[Tags.Dark] = -100
	unit.resists[Tags.Arcane] = -50
	
	if spell != None:
		unit.buffs.append(HealAuraBuff(5, spell.get_stat('radius')) )
	else:
		unit.buffs.append(HealAuraBuff(2,4) )
	unit.buffs.append(SlimePriestGrowth(spell))
	##unit.is_coward = True ##Work this into a different spell?
	return unit


def ShieldKnight():
	unit = Unit()
	unit.name = "Tower Knight"
	unit.asset = ["TcrsCustomModpack", "Units", "shield_knight"]

	unit.max_hp = 80
	unit.shields = 8
	
	unit.tags = [Tags.Arcane, Tags.Metallic, Tags.Living]
	unit.resists[Tags.Arcane] = 75
	unit.resists[Tags.Fire] = 50
	unit.resists[Tags.Lightning] = 50
	unit.resists[Tags.Ice] = 50

	def shield_on_hit(knight, target):
		if knight.shields <= 8:
			knight.shields += 1
	melee = SimpleMeleeAttack(damage=10, damage_type=Tags.Physical, onhit=shield_on_hit)
	melee.description  = "Gain 1 shield on hit, up to 4"
	unit.spells.append(melee)
	unit.buffs.append(ShieldRegenBuff(shield_freq=3, shield_max=8))
	
	return unit


def MaterialSlimeRandomize():
	tags = [Tags.Slime]
	if random.randint(1,3) == 1:
		tags.append(Tags.Dragon)
	if random.randint(1,3) == 1:
		tags.append(Tags.Metallic)
	return tags

def MaterialSlime(tags=[]):
	unit = Unit()
	unit.name = "Woven Slime"
	unit.description = "A slime woven from magic"
	unit.max_hp = 15
	unit.resists[Tags.Poison] = 100

	if tags == []:
		tags = MaterialSlimeRandomize()
	unit.tags = tags
	unit.max_hp *= len(tags)
	unit.spells.append(SimpleMeleeAttack(5*len(tags)))

	suffix = "_"
	if Tags.Slime in tags:
		unit.buffs.append(SlimeBuff(MaterialSlime))
		suffix += "n"
	if Tags.Dragon in tags:
		unit.name  += " Whelp"
		poison_breath = FireBreath()
		poison_breath.damage_type = Tags.Poison
		poison_breath.damage *= len(tags)
		poison_breath.name = "Poison Breath"
		unit.spells.append(poison_breath)
		suffix += "r"
	if Tags.Metallic in tags:
		unit.buffs.append(Thorns(6*len(tags), Tags.Physical))
		unit.name += " Spiker"
		suffix += "m"
	unit.asset = ["TcrsCustomModpack", "Units-Variant", "matslime" + suffix]

	return unit




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


class SilkBreath(BreathWeapon):
	def __init__(self, skill=None):
		BreathWeapon.__init__(self)
		self.name = "Web Spew"
		if skill:
			self.skill = skill
		self.damage = 2
		self.duration = 12
		self.damage_type = Tags.Poison
		self.cool_down = 14
		self.range = 8
		self.angle = math.pi / 5.0

	def get_description(self):
		return "Produces webs which last for 12 turns."

	def per_square_effect(self, x, y):
		cloud = SpiderWeb()
		cloud.owner = self.owner
		self.caster.level.add_obj(cloud, x, y)
		self.caster.level.deal_damage(x, y, self.damage, Tags.Poison, self)

def SpiderDragon(skill=None):
	unit = Unit()
	unit.name = "Silkwyrm"
	unit.asset = ["TcrsCustomModpack", "Units", "wyrm_spider"] ##Modified aelf spider sprite plus wyrm. Very derivative
	unit.max_hp = 75

	def StunDmgBonus(owner, target):
		if not target:
			return
		if target.has_buff(Stun):
			target.deal_damage(44, Tags.Poison, melee)
	melee = SimpleMeleeAttack(16, onhit=StunDmgBonus)
	melee.description = "Deals 44 bonus [poison] damage to stunned targets."
	unit.spells.append(melee)
	breath = SilkBreath(skill)
	unit.spells.append(breath)
	websling = PullAttack(damage=2,damage_type=Tags.Physical,range=5,pull_squares=5,color=Tags.Tongue.color)
	websling.cool_down = 3
	unit.spells.append(websling)

	unit.tags = [Tags.Spider, Tags.Dragon, Tags.Living]
	unit.resists[Tags.Poison] = 100
	unit.resists[Tags.Fire] = -100
	return unit


class TiamatBreath(BreathWeapon):
	def __init__(self):
		BreathWeapon.__init__(self)
		self.name = "Pyrostatic Breath"
		self.damage = 12
		self.description = "Deals [Fire] or [Lightning] damage in a cone."
		def random_type():
			return random.choice([Tags.Fire, Tags.Lightning])
		self.damage_type = random_type()
		self.cool_down = 3
		self.range = 4
		self.angle = math.pi / 6.0


	def per_square_effect(self, x, y):
		unit = self.caster.level.get_unit_at(x, y)
		tag = random.choice([Tags.Fire, Tags.Lightning])
		if unit:
			self.caster.level.deal_damage(x, y, self.damage, tag, self)
		else:
			self.caster.level.show_effect(x, y, tag, minor=True)


class TiamatAvatarGrowth(Buff):
	def __init__(self, spell=None):
		Buff.__init__(self)
		self.spell = spell
		self.color = Tags.Chaos.color
		self.name = "Consuming Wyrm"
		self.description = ("On kill, steal 10% of the targets max life, and 20% of the damage from their spell's with damage.")
		self.buff_type = BUFF_TYPE_BLESS
		self.global_triggers[EventOnDeath] = self.on_death

	def on_death(self, evt):
		if not (evt.damage_event and evt.damage_event.source and evt.damage_event.source.owner == self.owner): ##TODO test for any events that might crash this, void bombers blowing up?
			return
		
		hp_bonus = evt.unit.max_hp // 10
		spell_dmg = 0
		for spell in evt.unit.spells:
			if not hasattr(spell, 'damage'):
				continue
			spell_dmg += spell.damage // 5
		buff = TiamatAvatarGrowStats(hp_bonus, spell_dmg)
		if self.spell == None:
			self.owner.apply_buff(buff, 10)
		else:
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


class PeriodicBerserking(Buff):
	def __init__(self):
		Buff.__init__(self)
		self.name = "Periodic Rage"
		self.buff_type = BUFF_TYPE_PASSIVE
		self.color = Tags.Chaos.color
		self.description = "Becomes berserk every 10 turns for 4 turns."
		self.stack_type = STACK_NONE
		self.count = 10

	def on_advance(self):
		self.count -= 1
		if self.count <= 0:
			self.count = 10
			buff = self.owner.get_buff(BerserkBuff)
			if buff == None:
				self.owner.apply_buff(BerserkBuff(), 4)
			else:
				buff.turns_left += 4

def Berserker(spell=None):
	unit = Unit()
	unit.asset = ["TcrsCustomModpack", "Units", "berserker"]
	unit.name = "Berserker"
	unit.description = "A crazed demon which attacks friend and foe."
	unit.max_hp = 113
	unit.spells.append(SimpleMeleeAttack(damage=14))
	unit.spells.append(LeapAttack(damage=14, damage_type=Tags.Physical, range=8, is_leap=False))
	unit.tags = [Tags.Demon, Tags.Chaos]
	if spell == None:
		unit.buffs.append(PeriodicBerserking())
	return unit

DIFF_EASY = 1
DIFF_MED = 2
DIFF_HARD = 3

import os
filename = os.path.join(os.getcwd(), 'mods','TcrsCustomModpack', 'config.txt')
with open(filename, 'r') as config:
	line = config.readline()
	if line.lower() == "spawn_monsters = true":
		spawn_options.extend( [ (Fishman, 2), (IceShambler_Med, 3), (SlimePriest, 3), (ChaosBeast, 4), (Riftstalker, 4), (SandElemental, 4), (FishmanArcher, 4), (FishmanCat, 4), (FishmanLion, 4), (IceShambler_Big, 5), (SeaSerpent_Unit, 5) ] )
		spawn_options.extend( [ (ShieldKnight, 6), (ChaosWyrm, 7), (SpiderDragon, 7), (VoidWyrm, 7), (GoldWyrm, 7), (ChiroDragon, 7), (GalvanizedHorror, 9) ] )
		new_spawns_rare = [ (Hydra, DIFF_EASY, 2, 3, None), (GristMage, DIFF_EASY, 1, 1, None), (Tachi, DIFF_EASY, 2, 5, None), (Berserker, DIFF_EASY, 5, 7, None) ]