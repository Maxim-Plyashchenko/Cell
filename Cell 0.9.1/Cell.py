import cv2
import numpy as np
import time as t
import math as m
import random as rnd
import datetime
from ctypes import windll

WIN_NAME = "Cell"
WIN_SIZE = (windll.user32.GetSystemMetrics(0),
			windll.user32.GetSystemMetrics(1))
del windll
EMPTY_FRAME = np.zeros(list(reversed(list(WIN_SIZE)))+[3], np.dtype("uint8"))
MY_GENOME = [154,250,4,3,	# energy > 250 ? goto line 3 : goto 2
			1,				# photosynthesis
			103,32,5,3,		# native cell at 1 ? goto line 5 : goto 4
			52,32,			# division to 1
			103,96,5,3,		# native cell at 3 ? goto line 7 : goto 6
			52,96,			# division to 3
			103,0,5,3,		# native cell at 0 ? goto line 9 : goto 8
			52,0,			# division to 0
			103,64,5,3,		# native cell at 64 ? goto line 11 : goto 10
			52,64,			# division to 64
			0,0,0]			# dead
			

'''world parameters'''
worldSize = (80,40)
worldSize = (35,32)
cellMap = np.full(list(reversed(list(worldSize))), None)
lightMap = np.zeros(list(reversed(list(worldSize))))
lightPos = 0
lightPosChangesDelay = 10 # in steps
lightStepSkipCounter = 0
startGenCodeLen = 32

'''monitors parameters'''
'''block_name = [top-left_point, right-bottom_point]'''
'''log monitor'''
logMonitor = [(WIN_SIZE[0]-250,0),(WIN_SIZE[0],WIN_SIZE[1])]
genCodeMonitor = [(logMonitor[0][0], logMonitor[1][1]-250), logMonitor[1]]
genCodeCtrlPanel = [(genCodeMonitor[0][0], genCodeMonitor[0][1]-1), (genCodeMonitor[1][0], genCodeMonitor[0][1]-30)]
'''time control monitor'''
timeControlMonitor = [(0,WIN_SIZE[1]-51),(logMonitor[0][0], WIN_SIZE[1]-1)]
pauseButton = [(round((timeControlMonitor[1][0]-timeControlMonitor[0][0])/2)+timeControlMonitor[0][0]-24, round((timeControlMonitor[1][1]-timeControlMonitor[0][1])/2)+timeControlMonitor[0][1]-24),
				(round((timeControlMonitor[1][0]-timeControlMonitor[0][0])/2)+timeControlMonitor[0][0]+26, round((timeControlMonitor[1][1]-timeControlMonitor[0][1])/2)+timeControlMonitor[0][1]+26)]
playButtonImg = cv2.imread("buttons\\play.png")
pauseButtonImg = cv2.imread("buttons\\pause.png")
speedZoomer = [(pauseButton[1][0],pauseButton[0][1]), (pauseButton[1][0]+250,pauseButton[1][1])]
'''world monitor'''
worldMonitor = [(100,100), (logMonitor[0][0], timeControlMonitor[0][1])]

'''interface parameters'''
cellSize = 19
selectedCell = None
logging = False

'''time control parameters'''
pause = True
stepDelay = 2
lastStep = t.time()

'''other parameters'''

'''DEBUG PARAMETERS'''
controlMode = None

mousePos = (0,0)
mouseLButtonDown = False
mouseRButtonDown = False
mouseLButtonClick = False
mouseRButtonClick = False
mouseWheel = False
def mouseListener(event, x, y, flag, params):
	global mousePos, \
			mouseLButtonDown, \
			mouseLButtonClick, \
			mouseRButtonDown, \
			mouseRButtonClick, \
			mouseWheel
	if event == cv2.EVENT_MOUSEMOVE: mousePos = (x,y)
	if event == cv2.EVENT_LBUTTONUP: mouseLButtonDown = False
	if event == cv2.EVENT_LBUTTONDOWN:
		mouseLButtonDown = True
		mouseLButtonClick = True
	if event == cv2.EVENT_RBUTTONUP: mouseRButtonDown = False
	if event == cv2.EVENT_RBUTTONDOWN:
		mouseRButtonDown = True
		mouseRButtonClick = True
	if event == cv2.EVENT_MOUSEWHEEL:
		if flag > 0: mouseWheel = "up"
		if flag < 0: mouseWheel = "down"


def lightMapFilling(lightPos):
	global lightMap
	lightMap = np.zeros(list(reversed(list(worldSize))))
	cellAng = round(m.radians(90) / (len(lightMap)/4), 2) # the angle occupied by each cell of one hemisphere
	for row in range(round(len(lightMap)/4)):
		for col in range(len(lightMap[row])):
			yPosUpp = row+lightPos if row+lightPos < len(lightMap) else row+lightPos-len(lightMap)
			# yPosUpp = None if row+lightPos+len(lightMap)+1 < len(lightMap)-1 else -1-row+lightPos
			yPosLow = -1-row+lightPos
			lightMap[yPosUpp][col] = abs(m.cos((row+1) * cellAng))
			lightMap[yPosLow][col] = abs(m.cos((row+1) * cellAng))
lightMapFilling(lightPos)


cellList = []
class Cell():
	def __init__(self, pos, energy, diet, geneticCode, mutaProbab):
		self.pos = pos
		self.energy = energy
		self.diet = diet
		self.geneticCode = geneticCode
		self.mutaProbab = mutaProbab

		'''life'''
		self.life = True
		self.age = 0
		self.maxAge = lightPosChangesDelay*worldSize[1]*3 # 3 days
		'''energy'''
		self.maxEnergy = 512
		self.maxEnergyFromLight = self.maxEnergy/10 # the amount of energy a cell can receive at maximum light
		self.dietChangeSpeed = 0.01 # 1 - maximum
		self.energyConsumpForMove = 5
		'''other'''
		self.wasAttacked = False
		self.curCommand = startGenCodeLen-1
		self.lastStep = t.time()

	def dirToPoint(self, course):
		'''converts a number from 0 to 7 into one of the neighboring cells with the corresponding number'''
		planPoint = list(self.pos)
		if course == 0 or course == 7 or course == 1:
			planPoint[1] -= 1 if planPoint[1] > 0 else -len(cellMap)+1
		if course == 2 or course == 1 or course == 3:
			planPoint[0] += 1 if planPoint[0] < len(cellMap[0])-1 else -len(cellMap[0])+1
		if course == 4 or course == 3 or course == 5:
			planPoint[1] += 1 if planPoint[1] < len(cellMap)-1 else -len(cellMap)+1
		if course == 6 or course == 5 or course == 7:
			planPoint[0] -= 1 if planPoint[0] > 0 else -len(cellMap[0])+1
		return planPoint

	def move(self, course):
		if self.energy >= self.energyConsumpForMove:
			planPoint = self.dirToPoint(course)
			if cellMap[planPoint[1]][planPoint[0]] == None:
				self.pos = list(planPoint)
				self.energy -= self.energyConsumpForMove

	def division(self, course):
		global cellMap
		if self.energy > 1:
			planPoint = self.dirToPoint(course)
			if cellMap[planPoint[1]][planPoint[0]] == None: 
				inheritedGeneticCode = list(self.geneticCode)
				inheritedMutaProbab = self.mutaProbab
				if rnd.randint(0, 100) < self.mutaProbab:
					inheritedMutaProbab = 100-int(m.sin(rnd.uniform(0.01, 1.57))*100)
					mutaGenNum = None
					for i in range(int(len(inheritedGeneticCode)/100*inheritedMutaProbab)):
						inheritedGeneticCode[rnd.randint(0, len(inheritedGeneticCode)-1)] = rnd.randint(0, 255)
						mutaGenNum = i
					if logging: print("#cell >> Аs a result of division, my descendant mutated!")

				cellList.append(Cell(planPoint, round(self.energy/2), list(self.diet), inheritedGeneticCode, inheritedMutaProbab))
				cellMap[planPoint[1]][planPoint[0]] = cellList[-1]
				self.energy = round(self.energy / 2)

	def bite(self, course):
		planPoint = self.dirToPoint(course)
		if cellMap[planPoint[1]][planPoint[0]] != None:
			victim = cellMap[planPoint[1]][planPoint[0]]

			if victim.energy >= int(round((self.energy/2) * self.diet[1])):
				self.energy += int(round((self.energy/2) * self.diet[1]))
			else:
				self.energy += victim.energy
			if self.energy > self.maxEnergy: self.energy = self.maxEnergy
			if self.diet[0] > self.dietChangeSpeed: self.diet[0] = self.diet[0] - self.dietChangeSpeed
			if self.diet[1] < 1: self.diet[1] = self.diet[1] + self.dietChangeSpeed

			victim.energy -= int(round((self.energy/2) * self.diet[1]))
			victim.wasAttacked = True

	def photosynthesis(self):
		self.energy += int(round(self.maxEnergyFromLight * self.diet[0] * lightMap[self.pos[1]][self.pos[0]]))
		if self.energy > self.maxEnergy: self.energy = self.maxEnergy
		if self.diet[0] < 1: self.diet[0] = self.diet[0] + self.dietChangeSpeed
		if self.diet[1] > self.dietChangeSpeed: self.diet[1] = self.diet[1] - self.dietChangeSpeed

	def geneticCodeHandler(self):
		self.curCommand += 1
		if self.curCommand == len(self.geneticCode): self.curCommand = 0
		command = self.geneticCode[self.curCommand]
		if logging: 
			print("\n#cell >> I am", str(self).split('.')[1][:-1])
			print("#cell >> My coordinates", self.pos)
			print("#cell >> My current command (" + str(self.curCommand) + "-th) is " + str(command) + '. It is', end=' ')
		commandTypeCoef = round(0xFF/5,3)

		# self action
		if command < int(commandTypeCoef*1):
			if logging: print("self action")
			commandCoef = round(commandTypeCoef/1)
			if command == 0:
				self.life = False
			elif command < commandCoef*1:
				if logging: print("#cell >> *carries out photosynthesis*")
				self.photosynthesis()
			self.curCommand = -1

		# directed action
		elif command < int(commandTypeCoef*2):
			if logging: print("directed action")
			commandCoef = round(commandTypeCoef/3)
			courseByte = self.curCommand+1 if self.curCommand+1 < len(self.geneticCode) else 0 
			course = int((8/0xFF)*self.geneticCode[courseByte])
			if command < int(commandTypeCoef*1) + commandCoef*1: 
				if logging: print("#cell >> I division to", self.dirToPoint(course))
				self.division(course)
			elif command < int(commandTypeCoef*1) + commandCoef*2: 
				if logging: print("#cell >> I move to", self.dirToPoint(course))
				self.move(course)
			elif command < int(commandTypeCoef*1) + commandCoef*3: 
				if logging: print("#cell >> I bite to", self.dirToPoint(course))
				self.bite(course)
			self.curCommand = -1

		# directional check for the presence
		elif command < int(commandTypeCoef*3):
			if logging: print("directional check for the presence")
			courseByte = self.curCommand+1 if self.curCommand+1 < len(self.geneticCode) else 0 
			course = int((8/0xFF)*self.geneticCode[courseByte])
			obserPoint = self.dirToPoint(course)

			# checking
			if cellMap[obserPoint[1]][obserPoint[0]] == None:
				if logging: print("#cell >> Any possible cell ", end='')
				detect = False
			else:
				commandCoef = round(commandTypeCoef/2)
				if command < int(commandTypeCoef*2) + commandCoef*1:
					if logging: print("#cell >> Native cell ", end='')
					if cellMap[obserPoint[1]][obserPoint[0]].geneticCode == self.geneticCode:
						detect = True
					else: detect = False
				elif command < int(commandTypeCoef*2) + commandCoef*2:
					if logging: print("#cell >> Non-native cell ", end='')
					if cellMap[obserPoint[1]][obserPoint[0]].geneticCode != self.geneticCode:
						detect = True
					else: detect = False
			if logging: print("in", obserPoint, end=' ')

			# transition
			if detect:
				if logging: print("detected")
				argCoef = self.curCommand+2 if self.curCommand+2 < len(self.geneticCode) else (self.curCommand+2)-len(self.geneticCode)
			else: 
				if logging: print("not detected")
				argCoef = self.curCommand+3 if self.curCommand+3 < len(self.geneticCode) else (self.curCommand+3)-len(self.geneticCode)
			if logging: print("#cell >> I go to",
				str(self.curCommand + self.geneticCode[argCoef]) + "-th byte",
				'(' + str(self.curCommand) + '+' + str(self.geneticCode[argCoef]) + ')', end=". ")
			self.curCommand += self.geneticCode[argCoef]

			# normalization 
			while self.curCommand >= len(self.geneticCode):
				self.curCommand -= len(self.geneticCode)
			if logging: print(str(self.curCommand) + "-th after normalization")

		# comparison of characteristics on yourself
		elif command < int(commandTypeCoef*4):
			if logging: print("comparison of characteristics on yourself")
			valueByte = self.curCommand+1 if self.curCommand+1 < len(self.geneticCode) else 0
			# value = int((8/0xFF)*self.geneticCode[courseByte])
			value = self.geneticCode[valueByte]

			# comparison
			commandCoef = round(commandTypeCoef/5)
			if command < int(commandTypeCoef*3) + commandCoef*1:
				value = int((self.maxEnergy/0xFF)*self.geneticCode[valueByte])
				if self.energy > value: 
					if logging: print("#cell >> Energy >", value, end='')
					ratio = '>'
				else:
					if logging: print("#cell >> Energy <", value, end='')
					ratio = '<'
			elif command < int(commandTypeCoef*3) + commandCoef*2:
				value = (1/0xFF)*self.geneticCode[valueByte]
				if lightMap[self.pos[1]][self.pos[0]] > value: 
					if logging: print("#cell >> Received light (" + str(round(lightMap[self.pos[1]][self.pos[0]], 3)) + ") >", round(value, 3), end='')
					ratio = '>'
				else:
					if logging: print("#cell >> Received light (" + str(round(lightMap[self.pos[1]][self.pos[0]], 3)) + ") <", round(value, 3), end='')
					ratio = '<'
			elif command < int(commandTypeCoef*3) + commandCoef*3:
				value = round((1/0xFF)*self.geneticCode[valueByte], 3)
				if self.diet[0] > value: 
					if logging: print("#cell >> Plant coefficient (" + str(self.diet[0]) + ") >", value, end='')
					ratio = '>'
				else:
					if logging: print("#cell >> Plant coefficient (" + str(self.diet[0]) + ") <", value, end='')
					ratio = '<'
			elif command < int(commandTypeCoef*3) + commandCoef*4:
				value = round((1/0xFF)*self.geneticCode[valueByte], 3)
				if self.diet[1] > value: 
					if logging: print("#cell >> Predator coefficient (" + str(self.diet[1]) + ") >", value, end='')
					ratio = '>'
				else:
					if logging: print("#cell >> Predator coefficient (" + str(self.diet[1]) + ") <", value, end='')
					ratio = '<'
			else:
				if logging: print("#cell >> ERROR: Temperature comparison is not available in this version. \"Less\" option will be selected", end='')
				ratio = '<'
				# if self.energy > value: 
				# 	if logging: print("#cell >> Temperature >", value, end='')
				# 	ratio = '>'
				# else:
				# 	if logging: print("#cell >> Temperature <", value, end='')
				#		ratio = '<'

			# transition
			if ratio == '>': # BUG IN THIS LINE
				argCoef = self.curCommand+2 if self.curCommand+2 < len(self.geneticCode) else (self.curCommand+2)-len(self.geneticCode)
			else: 
				argCoef = self.curCommand+3 if self.curCommand+3 < len(self.geneticCode) else (self.curCommand+3)-len(self.geneticCode)
			if logging: print(", so I go to",
				str(self.curCommand + self.geneticCode[argCoef]) + "-th byte",
				'(' + str(self.curCommand) + '+' + str(self.geneticCode[argCoef]) + ')', end=". ")
			self.curCommand += self.geneticCode[argCoef]
			self.curCommand %= len(self.geneticCode)
			if logging: print(str(self.curCommand) + "-th after normalization")

		# directed comparison of characteristics
		elif command <= int(commandTypeCoef*5):
			if logging: print("directed comparison of characteristics")
			courseByte = self.curCommand+1 if self.curCommand+1 < len(self.geneticCode) else 0 
			course = int((8/0xFF)*self.geneticCode[courseByte])
			obserPoint = self.dirToPoint(course)
			valueByte = (self.curCommand+1) % len(self.geneticCode)
			value = self.geneticCode[valueByte]

			# comparison
			commandCoef = round(commandTypeCoef/5)
			if command < int(commandTypeCoef*4) + commandCoef*1:
				value = int((self.maxEnergy/0xFF)*self.geneticCode[valueByte])
				if cellMap[obserPoint[1]][obserPoint[0]] == None:
					if logging: print("#cell >> Cell not found in", obserPoint, end='')
					ratio = '<'
				else:
					if cellMap[obserPoint[1]][obserPoint[0]].energy > value:
						if logging: print("#cell >> Energy (" + str(cellMap[obserPoint[1]][obserPoint[0]].energy) + ") in", obserPoint, '>', value, end='')
						ratio = '>'
					else:
						if logging: print("#cell >> Energy (" + str(cellMap[obserPoint[1]][obserPoint[0]].energy) + ") in", obserPoint, '<', value, end='')
						ratio = '<'

			elif command < int(commandTypeCoef*4) + commandCoef*1:
				value = (1/0xFF)*self.geneticCode[valueByte]
				if lightMap[obserPoint[1]][obserPoint[0]] > value:
					if logging: print("#cell >> Received light (" + str(round(lightMap[obserPoint[1]][obserPoint[0]],3)) + ") in", obserPoint, '>', round(value,3), end='')
					ratio = '>'
				else:
					if logging: print("#cell >> Received light (" + str(round(lightMap[obserPoint[1]][obserPoint[0]],3)) + ") in", obserPoint, '<', round(value,3), end='')
					ratio = '<'
			elif command < int(commandTypeCoef*4) + commandCoef*2:
				if cellMap[obserPoint[1]][obserPoint[0]] == None:
					if logging: print("#cell >> Cell not found in", obserPoint, end='')
					ratio = '<'
				else:
					if cellMap[obserPoint[1]][obserPoint[0]].diet[0] > value:
						if logging: print("#cell >> Plant coefficient (" + str(cellMap[obserPoint[1]][obserPoint[0]].diet[0]) + ") in", obserPoint, '>', value, end='')
						ratio = '>'
					else:
						if logging: print("#cell >> Plant coefficient (" + str(cellMap[obserPoint[1]][obserPoint[0]].diet[0]) + ") in", obserPoint, '<', value, end='')
						ratio = '<'
			elif command < int(commandTypeCoef*4) + commandCoef*3:
				if cellMap[obserPoint[1]][obserPoint[0]] == None:
					if logging: print("#cell >> Cell not found in", obserPoint, end='')
					ratio = '<'
				else:
					if cellMap[obserPoint[1]][obserPoint[0]].diet[1] > value:
						if logging: print("#cell >> Predator coefficient (" + str(cellMap[obserPoint[1]][obserPoint[0]].diet[1]) + ") in", obserPoint, '>', value, end='')
						ratio = '>'
					else:
						if logging: print("#cell >> Predator coefficient (" + str(cellMap[obserPoint[1]][obserPoint[0]].diet[1]) + ") in", obserPoint, '<', value, end='')
						ratio = '<'
			else:
				if logging: print("#cell >> ERROR: Temperature comparison is not available in this version. \"Less\" option will be selected", end='')
				ratio = '<'
				# value = int((self.maxEnergyFromLight/0xFF)*self.geneticCode[valueByte])
				# if int(round(self.maxEnergyFromLight * self.diet[0] * lightMap[obserPoint[1]][obserPoint[0]])) > value:
				# 	if logging: print("#cell >> Temperature (" + str(temperatureMap[obserPoint[1]][obserPoint[0]]) + ") in", obserPoint, '>', value, end='')
				# 	ratio = '>'
				# else:
				# 	if logging: print("#cell >> Temperature (" + str(temperatureMap[obserPoint[1]][obserPoint[0]]) + ") in", obserPoint, '<', value, end='')
				# 	ratio = '<'

			# transition
			if ratio == '>':
				argCoef = self.curCommand+2 if self.curCommand+2 < len(self.geneticCode) else (self.curCommand+2)-len(self.geneticCode)
			else: 
				argCoef = self.curCommand+3 if self.curCommand+3 < len(self.geneticCode) else (self.curCommand+3)-len(self.geneticCode)
			if logging: print(", so I go to",
				str(self.curCommand + self.geneticCode[argCoef]) + "-th byte",
				'(' + str(self.curCommand) + '+' + str(self.geneticCode[argCoef]) + ')', end=". ")
			self.curCommand += self.geneticCode[argCoef]
			self.curCommand %= len(self.geneticCode)
			if logging: print(str(self.curCommand) + "-th after normalization")

		if logging: print("#cell >> It's all. Till!\n")


def saveGenome(genome):
	fileName = list(datetime.datetime.now().isoformat().split('.')[0])
	for i in range(len(fileName)):
		if fileName[i] == ':':
			fileName[i] = '-'
	fileName = ''.join(fileName)
	outFile = open(fileName+".genome", 'w')
	outFile.write(str(genome)[1:-1])
	outFile.close()


cellList.append(Cell(
				[4,5],	# pos
				512,	# energy
				[1, 0.01], # diet
				# [rnd.randint(0, 0xFF) for i in range(startGenCodeLen)], # geneticCode
				MY_GENOME, # geneticCode
				20 # mutaProbab
				))

if logging: print(cellList[0].geneticCode)


'''window setup'''
cv2.namedWindow(WIN_NAME, cv2.WND_PROP_FULLSCREEN)
cv2.setWindowProperty(WIN_NAME, cv2.WND_PROP_FULLSCREEN, cv2.WINDOW_FULLSCREEN)
cv2.setMouseCallback(WIN_NAME, mouseListener)

mainCycleLife = True
while mainCycleLife:
	'''reset'''

	'''install'''
	logList = []
	frame = np.array(EMPTY_FRAME)
	mouseWheel = False
	mouseLButtonClick = False
	mouseRButtonClick = False

	if (not pause) and t.time() - lastStep >= stepDelay:
		lastStep = t.time()
		lightStepSkipCounter += 1
		if lightStepSkipCounter >= lightPosChangesDelay:
			lightStepSkipCounter = 0
			lightPos += 1 if lightPos < worldSize[1] else -worldSize[1]
			lightMapFilling(lightPos)
	logList.append(lightPos)

	cellMap = np.full(list(reversed(list(worldSize))), None)
	for cell in cellList: cellMap[cell.pos[1]][cell.pos[0]] = cell

	'''key processing'''
	key = cv2.waitKeyEx(1)
	if key == 27: # esc
		mainCycleLife = False
	if key == 2424832: 	# left
		pass
	if key == 2555904: 	# right
		pass
	if key == 2490368: 	# up
		pass
	if key == 2621440: 	# down
		pass
	if key == 32: 		# space
		pause = not pause

	'''light map drawing'''
	for yPos in range(len(lightMap)):
		for xPos in range(len(lightMap[0])):
			blue = 255 + 0 * lightMap[yPos][xPos]
			green = 0 + 255 * lightMap[yPos][xPos]
			red = 0 + 255 * lightMap[yPos][xPos]
			cv2.rectangle(frame,
						(xPos*cellSize+worldMonitor[0][0], yPos*cellSize+worldMonitor[0][1]), 
						(xPos*cellSize+worldMonitor[0][0] + cellSize, yPos*cellSize+worldMonitor[0][1] + cellSize), 
						(blue,green,red), -1)
		cv2.line(frame,
			(worldMonitor[0][0]-int(round(50*lightMap[yPos][xPos])), yPos*cellSize+round(cellSize/2)+worldMonitor[0][1]),
			(worldMonitor[0][0]-round(cellSize/2), yPos*cellSize+round(cellSize/2)+worldMonitor[0][1]),
			(blue, green, red), cellSize)

	'''cell processing'''
	oldCellMap = np.array(cellMap)
	for cell in cellList:
		if cell.energy < 1 or cell.age >= cell.maxAge: cell.life = False
		if cell.life:
			cellMap[cell.pos[1]][cell.pos[0]] = cell

			if (not pause) and t.time() - cell.lastStep >= stepDelay:
				cell.lastStep = t.time()
				cell.geneticCodeHandler()
				cell.energy -= 1
				cell.age += 1

			'''cell drawing'''
			blue = 0
			green = cell.diet[0] * 512
			red = cell.diet[1] * 512
			# cv2.rectangle(frame,
			# 			(cell.pos[0]*cellSize+worldMonitor[0][0], cell.pos[1]*cellSize+worldMonitor[0][1]), 
			# 			(cell.pos[0]*cellSize+cellSize+worldMonitor[0][0], cell.pos[1]*cellSize+cellSize+worldMonitor[0][1]), 
			# 			(blue,green,red), -1)
			cv2.circle(frame,
				(cell.pos[0]*cellSize+worldMonitor[0][0] + int(cellSize/2), cell.pos[1]*cellSize+worldMonitor[0][1] + int(cellSize/2)),
				int(cellSize/2), 
				(blue,green,red), -1)
			if cell == selectedCell:
				cv2.rectangle(frame, (cell.pos[0]*cellSize+worldMonitor[0][0], cell.pos[1]*cellSize+worldMonitor[0][1]), 
									(cell.pos[0]*cellSize+cellSize+worldMonitor[0][0], cell.pos[1]*cellSize+cellSize+worldMonitor[0][1]), 
									(0,0,0), 3)
	cellList = [cell for cell in cellList if cell.life]
	logList.append(len(cellList))


	'''grid drawing'''
	for yPos in range(worldSize[1]):
		for xPos in range(worldSize[0]):
			cv2.rectangle(frame, 
						(xPos*cellSize+worldMonitor[0][0], yPos*cellSize+worldMonitor[0][1]), 
						(xPos*cellSize+worldMonitor[0][0] + cellSize, yPos*cellSize+worldMonitor[0][1] + cellSize), 
						(64,64,64))

	'''if the mouse is in world space'''
	if worldMonitor[0][0] <= mousePos[0] < worldMonitor[0][0] + worldSize[0] * cellSize and \
			worldMonitor[0][1] <= mousePos[1] < worldMonitor[0][1] + worldSize[1] * cellSize:
		focusCell = [(mousePos[0]-worldMonitor[0][0])//cellSize,
							(mousePos[1]-worldMonitor[0][1])//cellSize]
		logList.append("FcsCll " + str(focusCell))

		'''specified cell drawing'''
		cv2.circle(frame, (round(focusCell[0]*cellSize+worldMonitor[0][0]+cellSize/2), 
							round(focusCell[1]*cellSize+worldMonitor[0][1]+cellSize/2)), 5, (0,0,0), -1)

		if cellMap[focusCell[1]][focusCell[0]] != None:
			if mouseLButtonClick:
				selectedCell = cellMap[focusCell[1]][focusCell[0]]
		else:
			if mouseLButtonClick:
				selectedCell = None
			if mouseRButtonClick:
				if controlMode == "newCellMaking":
					cellList.append(Cell(
						[focusCell[0],focusCell[1]],	# pos
						128,	# energy
						[1, 0.1], # diet
						[rnd.randint(0, 0xFF) for i in range(startGenCodeLen)], # geneticCode
						# [0 for i in range(startGenCodeLen)], # geneticCode
						20 # mutaProbab
						))

	'''blocks drawing'''
	# cv2.rectangle(frame, (0,0), (1024,600), (0,255,255))
	cv2.rectangle(frame, worldMonitor[0], worldMonitor[1], (255,32,32))
	cv2.rectangle(frame, logMonitor[0], logMonitor[1], (32,255,32))
	cv2.rectangle(frame, worldMonitor[0], (worldMonitor[0][0]+worldSize[0]*cellSize, worldMonitor[0][1]+worldSize[1]*cellSize), (32,32,255))
	cv2.rectangle(frame, timeControlMonitor[0], timeControlMonitor[1], (32,32,255))
	cv2.rectangle(frame, (speedZoomer[0][0], speedZoomer[0][1]-1), (speedZoomer[1][0], speedZoomer[1][1]-1), (255,255,255))

	'''time block drawing'''
	frame[pauseButton[0][1]:pauseButton[1][1], pauseButton[0][0]:pauseButton[1][0]] = playButtonImg if pause else pauseButtonImg
	cv2.rectangle(frame, (pauseButton[0][0], pauseButton[0][1]-1), (pauseButton[1][0], pauseButton[1][1]-1), (255,255,255))
	cv2.putText(frame, "delay = " + str(stepDelay) + " s", (speedZoomer[0][0]+5, speedZoomer[1][1]-15), cv2.FONT_HERSHEY_DUPLEX, 1, (0,255,0))
	if pauseButton[0][0] <= mousePos[0] < pauseButton[1][0] and \
			pauseButton[0][1] <= mousePos[1] < pauseButton[1][1]:
		cv2.rectangle(frame, (pauseButton[0][0],pauseButton[0][1]-1), (pauseButton[1][0],pauseButton[1][1]-1), (0,128,255))
		if mouseLButtonClick:
			pause = not pause
	if speedZoomer[0][0] <= mousePos[0] < speedZoomer[1][0] and \
			speedZoomer[0][1] <= mousePos[1] < speedZoomer[1][1]:
		cv2.rectangle(frame, (speedZoomer[0][0],speedZoomer[0][1]-1), (speedZoomer[1][0],speedZoomer[1][1]-1), (0,128,255))
		if mouseWheel == "up" and stepDelay < 2:
			stepDelay += .5
		elif mouseWheel == "down" and stepDelay > 0:
			stepDelay -= .5
		else: pass

	'''cell state drawing'''
	if selectedCell != None:
		if selectedCell.life == False:
			cv2.putText(frame, "Cell is dead...",
				(logMonitor[0][0]+10, 1*50),
				cv2.FONT_HERSHEY_DUPLEX, 1, (0,0,255))
		else:
			cv2.putText(frame, "Pos " + str(tuple(selectedCell.pos)),
				(logMonitor[0][0]+10, 1*20),
				cv2.FONT_HERSHEY_PLAIN, 1, (255,255,255))
			cv2.putText(frame, "Energy " + str(selectedCell.energy),
				(logMonitor[0][0]+10, 2*20),
				cv2.FONT_HERSHEY_PLAIN, 1, (255,255,255))
			red = round(512 / selectedCell.maxAge * selectedCell.age)
			green = 512 - red
			cv2.putText(frame, "Age " + str(selectedCell.age) + " (" + str(selectedCell.maxAge) + " - max.)",
				(logMonitor[0][0]+10, 3*20),
				cv2.FONT_HERSHEY_PLAIN, 1, (0,green,red))
			cv2.putText(frame, "Probability mutation = " + str(selectedCell.mutaProbab),
				(logMonitor[0][0]+10, 4*20),
				cv2.FONT_HERSHEY_PLAIN, 1, (255,255,0))
			cv2.putText(frame, "Light coef = " + str(round(lightMap[selectedCell.pos[1]][selectedCell.pos[0]], 3)),
				(logMonitor[0][0]+10, 5*20),
				cv2.FONT_HERSHEY_PLAIN, 1, (0,255,255))
			cv2.putText(frame,
				"Energy from light = " + str(round(selectedCell.maxEnergyFromLight * selectedCell.diet[0] * lightMap[selectedCell.pos[1]][selectedCell.pos[0]])),
				(logMonitor[0][0]+10, 6*20),
				cv2.FONT_HERSHEY_PLAIN, 1, (0,255,0))
			cv2.putText(frame, "Plant coef = " + str(selectedCell.diet[0]),
				(logMonitor[0][0]+10, 7*20),
				cv2.FONT_HERSHEY_PLAIN, 1, (0,255,0))
			cv2.putText(frame,
				"Energy from bite = " + str(round((selectedCell.energy/2) * selectedCell.diet[1])),
				(logMonitor[0][0]+10, 8*20),
				cv2.FONT_HERSHEY_PLAIN, 1, (64,128,255))
			cv2.putText(frame, "Predator coef = " + str(selectedCell.diet[1]),
				(logMonitor[0][0]+10, 9*20),
				cv2.FONT_HERSHEY_PLAIN, 1, (64,128,255))
			if selectedCell.wasAttacked:
				cv2.putText(frame, "Cell was attacked",
					(logMonitor[0][0]+10, 10*20),
					cv2.FONT_HERSHEY_PLAIN, 1, (0,0,255))

			'''genetic code control panel'''
			width = 60
			'''save button'''
			if genCodeCtrlPanel[0][0] < mousePos[0] < genCodeCtrlPanel[0][0]+width and \
					genCodeCtrlPanel[0][1] > mousePos[1] > genCodeCtrlPanel[1][1]:
				color = (0,128,255)
				if mouseLButtonClick:
					saveGenome(selectedCell.geneticCode)
			else: color = (255,255,255)
			cv2.rectangle(frame, 
				genCodeCtrlPanel[0], (genCodeCtrlPanel[0][0]+width, genCodeCtrlPanel[1][1]), 
				color)
			cv2.putText(frame, "Save",
				(genCodeCtrlPanel[0][0]+10, genCodeCtrlPanel[0][1]-10), 
				cv2.FONT_HERSHEY_PLAIN, 1, (255,255,255))

			'''cell genetical code drawing'''
			cv2.rectangle(frame, genCodeMonitor[0], genCodeMonitor[1], (255,0,0))
			genSqrS = int(m.sqrt(len(selectedCell.geneticCode))+1)
			genCellS = round(250//genSqrS)
			i = 0
			for yPos in range(genSqrS):
				for xPos in range(genSqrS):
					if i < len(selectedCell.geneticCode):
						color = (selectedCell.geneticCode[i], selectedCell.geneticCode[i], selectedCell.geneticCode[i])
						cv2.rectangle(frame, 
									(xPos*genCellS+genCodeMonitor[0][0], yPos*genCellS+genCodeMonitor[0][1]), 
									(xPos*genCellS+genCodeMonitor[0][0] + genCellS, yPos*genCellS+genCodeMonitor[0][1] + genCellS), 
									color, -1)
						cv2.rectangle(frame, 
									(xPos*genCellS+genCodeMonitor[0][0], yPos*genCellS+genCodeMonitor[0][1]), 
									(xPos*genCellS+genCodeMonitor[0][0] + genCellS, yPos*genCellS+genCodeMonitor[0][1] + genCellS), 
									(64,64,64))
					else:
						cv2.rectangle(frame, 
									(xPos*genCellS+genCodeMonitor[0][0], yPos*genCellS+genCodeMonitor[0][1]), 
									(xPos*genCellS+genCodeMonitor[0][0] + genCellS, yPos*genCellS+genCodeMonitor[0][1] + genCellS), 
									(0,128,255), -1)
					i += 1
			cv2.rectangle(frame,
						(selectedCell.curCommand%genSqrS*genCellS+genCodeMonitor[0][0], 
							(selectedCell.curCommand//genSqrS)*genCellS+genCodeMonitor[0][1]), 
						(selectedCell.curCommand%genSqrS*genCellS+genCodeMonitor[0][0] + genCellS, 
							(selectedCell.curCommand//genSqrS)*genCellS+genCodeMonitor[0][1] + genCellS), 
						(0,128,255), 3)
			'''if mouse is in genetical code cell'''
			if genCodeMonitor[0][0] <= mousePos[0] < genCodeMonitor[0][0] + genCellS * genSqrS and \
					genCodeMonitor[0][1] <= mousePos[1] < genCodeMonitor[0][1] + genCellS * genSqrS:
				focusGenCell = [(mousePos[0]-genCodeMonitor[0][0])//genCellS,
									(mousePos[1]-genCodeMonitor[0][1])//genCellS]
				focusGenCellId = focusGenCell[0]+focusGenCell[1]*genSqrS
				logList.append("FcsGenCll " + str(focusGenCell))
				cv2.circle(frame, 
					(focusGenCell[0]*genCellS+genCodeMonitor[0][0] + round(genCellS/2), 
						focusGenCell[1]*genCellS+genCodeMonitor[0][1] + round(genCellS/2)), 
					5, (0,128,255), -1)
				if focusGenCellId < len(selectedCell.geneticCode):
					cv2.rectangle(frame,
						(mousePos[0]-90, mousePos[1]-75),
						(mousePos[0], mousePos[1]-45),
						(0,15,30), -1)
					cv2.rectangle(frame,
						(mousePos[0]-90, mousePos[1]-75),
						(mousePos[0], mousePos[1]-45),
						(0,128,255))
					cv2.putText(frame,
						str(selectedCell.geneticCode[focusGenCellId]),
						(mousePos[0]-75, mousePos[1]-50),
						cv2.FONT_HERSHEY_DUPLEX, 1, (0,128,255))
					if mouseWheel == "up":
						if selectedCell.geneticCode[focusGenCellId] < 0xFF:
							if mouseRButtonDown and selectedCell.geneticCode[focusGenCellId] < 0xFF-10:
								selectedCell.geneticCode[focusGenCellId] += 10
							else: selectedCell.geneticCode[focusGenCellId] += 1
					elif mouseWheel == "down":
						if selectedCell.geneticCode[focusGenCellId] > 0:
							if mouseRButtonDown and selectedCell.geneticCode[focusGenCellId] > 10:
								selectedCell.geneticCode[focusGenCellId] -= 10
							else: selectedCell.geneticCode[focusGenCellId] -= 1 


	### DEBUG BLOCK ###
	'''experimental cell control'''
	if key == ord('m'): controlMode = "move"
	if key == ord('d'): controlMode = "division"
	if key == ord('b'): controlMode = "bite"
	if key == 13: controlMode = "newCellMaking"
	if selectedCell != None:
		if 48 <= key <= 57 and key != ord('5'):
			if   key == ord('8'): argument = 0
			elif key == ord('9'): argument = 1
			elif key == ord('6'): argument = 2
			elif key == ord('3'): argument = 3
			elif key == ord('2'): argument = 4
			elif key == ord('1'): argument = 5
			elif key == ord('4'): argument = 6
			elif key == ord('7'): argument = 7

			if controlMode == "move": selectedCell.move(argument)
			if controlMode == "division": selectedCell.division(argument)
			if controlMode == "bite": selectedCell.bite(argument)

		if key == ord('p'):
				controlMode = "photosynthesis"
				selectedCell.photosynthesis()
		if key == 3014656:
				controlMode = "dead"
				selectedCell.energy = 0

	logList.append("Mode = " + str(controlMode))
	# logList.append("LBDwn = " + str(mouseLButtonDown))
	# logList.append("LBClk = " + str(mouseLButtonClick))
	# logList = lightMap
	for i in range(len(logList)):
		cv2.putText(frame, str(logList[i]), (0,i*40+40), cv2.FONT_HERSHEY_DUPLEX, 1, (0,255,255))

	cv2.imshow(WIN_NAME, frame)
