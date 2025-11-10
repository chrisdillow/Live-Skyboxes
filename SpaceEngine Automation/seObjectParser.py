#SpaceEngine Object File Parsing
#Chris D.
#Version 0 | Version Date: 11/9/2025

#============================================================#
#|                    PROGRAM DESCRIPTION                   |#
#============================================================#
#Grabs necessary data from SpaceEngine files for the user.

#============================================================#
#|                    IMPORTS AND GLOBALS                   |#
#============================================================#
import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple

_BLOCK_OPEN = re.compile(r'^\s*(\w+)\s*(?:"([^"]+)")?\s*\{\s*$')
_BLOCK_CLOSE = re.compile(r'^\s*\}\s*$')
_KV_LINE = re.compile(r'^\s*([A-Za-z_]\w*)\s+([^\s/][^/]*)') # 'KV' for 'Key-Value'
_NUM_UNIT = re.compile(r'^\s*([+-]?\d+(?:\.\d+)?)(?:\s*(h|hr|hrs|hour|hours|d|day|days|yr|year|years))?\s*$',
                    re.IGNORECASE)

#============================================================#
#|                   FUNCTIONS AND HELPERS                  |#
#============================================================#
class Block:
    def __init__(self,type: str,name: Optional[str],parent: Optional['Block']=None):
        self.type = type
        self.name = name
        self.parent = parent
        self.keyValue: Dict[str,str] = {}
        self.children: List['Block'] = []
    
    def findChild(self,type: str,name: Optional[str]=None) -> Optional['Block']:
        for child in self.children:
            if child.type == type and (name is None or child.name == name):
                return child
        return None
    
def readText(path: str) -> str:
    return Path(path).readText(encoding="utf-8",errors="ignore")

def writeTXTcopy(srcPath: str,debugDir: Optional[str]) -> Optional[str]:
    if not debugDir:
        return None
    path = Path(srcPath)
    outPath = Path(debugDir) / (path.stem + ".txt")
    outPath.parent.mkdir(parents=True,exist_ok=True)
    outPath.write_text(readText(srcPath),encoding="utf-8",errors="ignore")
    return str(outPath)

def parseBlocks(text: str) -> List[Block]:
    roots = List[Block] = []
    stack = List[Block] = []
    
    for raw in text.splitlines():
        line = raw.split("//",1)[0] # Strip any // comments
        if not line.strip():
            continue

        matchOpen = _BLOCK_OPEN.match(line)
        if matchOpen:
            block = Block(matchOpen.group(1),matchOpen.group(2),stack[-1] if stack else None)
            if stack:
                stack[-1].children.append(block)
            else:
                roots.append(block)
            stack.append(block)
            continue

        matchKeyValue = _KV_LINE.match(line)
        if matchKeyValue and stack:
            key,value = matchKeyValue.group(1),matchKeyValue.group(2).strip()
            if len(value) >= 2 and ((value[0] == '"' and value[-1] == '"') or (value[0] == "'" and value[-1] == "'")):
                value = value[1:-1]
            stack[-1].keyValue[key] = value
            continue

    return roots

def findBlock(roots: List[Block],type: str,name: Optional[str]=None) -> Optional[Block]:
    queue = roots[:]
    while queue:
        block = queue.pop(0)
        if block.type == type and (name is not None or block.name == name):
            return block
        queue.extend(block.children)
    return None

def getValue(block: Block,key: str,default: Optional[str]=None) -> Optional[str]:
    return block.keyValue.get(key,default)

def numToHours(time: str) -> Optional[float]:
    unitMatch = _NUM_UNIT.match(time)
    if not unitMatch:
        return None
    value = float(unitMatch.group(1))
    unit = (unitMatch.group(2) or "").lower()
    if unit in ("h","hr","hrs","hour","hours",""):
        return value
    if unit in ("d","day","days"):
        return value * 24.0 #TODO: Determine if this needs to be based on Earth hours or the planet's hours
    if unit in ("yr","year","years"):
        return value * 24.0 * 365.0 #TODO: see above
    return None

def hoursToDays(hours: float,dayHours: float) -> float:
    return hours / max(dayHours,1e-9)

def buildCalendarSpec(roots: List[Block],planetName: Optional[str]=None,chosenMoon: Optional[str]=None,
                    fallbackDayHours: float=24.0,fallbackYearDays: float=365.0) -> Dict[str,float]:
    planet = findBlock(roots,"Planet",planetName) or findBlock(roots,"Planet")

    # ----- Day Length ----- #
    dayHours = fallbackDayHours
    for key in ("RotationPeriod","SiderealDay","DayLength","RotationalPeriodHours"):
        value = planet and getValue(planet,key)
        if value:
            potentialHours = numToHours(value)
            if potentialHours is not None:
                dayHours = potentialHours
                break
    
    # ----- Year Length ----- #
    yearDays = fallbackYearDays
    orbit = planet and planet.findChild("Orbit")
    if orbit:
        value = getValue(orbit,"Period")
        if value:
            hours = numToHours(value)
            if hours is not None:
                yearDays = hoursToDays(hours,dayHours)
    
    # ----- Month Length ----- #
    monthDays = 30.0
    if chosenMoon:
        moon = findBlock(roots,"Moon",chosenMoon) or findBlock(roots,"Body",chosenMoon)
        if moon:
            moonOrbit = moon.findChild("Orbit")
            if moonOrbit:
                value = getValue(moonOrbit,"Period")
                if value:
                    hours = numToHours(value)
                    if hours is not None:
                        monthDays = hoursToDays(hours,dayHours)
    
    return {
        "dayHours": dayHours,
        "monthDays": monthDays,
        "yearDays": yearDays,
        "year0": 2000, #TODO: Add option to let user set start year
    }