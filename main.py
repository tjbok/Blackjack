# Fun little hobby project to derive optimal strategy for Blackjack

import random

# If dealer starts with 21, the hand will be over without any option to hit/stand/split/double.
# This means that for strategy purposes, you can assume that if a dealer shows an Ace, the down
#  card can't be a 10, J, Q, or K
dealer_cant_start_with_21 = True

# Two other common rules variations
dealer_hit_on_soft_17 = True
allow_double_after_split = True

# We assume that you can't resplit pairs (split, then split a second time if you get dealt another of the same card)
#  and an infinite shoe (not 6-deck or 1-deck)

# This is a class that owns the dealer's 'strategy'
class Dealer:
    
    # Recursive function that returns a vector of probabilities that the dealer with the sp[ecified hand
    #  ends up with 17, 18, 19, 20, 21, or BUST (22).
    def evaluateDealerHand(hand=[], indent='  ', verbose = False):
        if verbose:
            print(indent + "EVALUATE " + str(hand))

        outcomes = {}
        
        # Determine if this hand is soft (aces counting as 11) or hard
        # Convention is that if aces can count as 11 without busting the hand, then score it as a soft
        #  hand with the ace counting as 11. (E.g. A + 5 is always considered a soft 16.)
        # If there are multiple aces, only one counts as 11.
        soft = False
        sum = 0
        for cardRank in hand:
            if (cardRank == 1) and not soft:
                sum += 11
                soft = True
            else:
                sum += min(cardRank, 10)

        # If a soft hand busts, try it again as a hard hand with the ace scoring as 1 instead of 11
        if (sum > 21) and soft:
            sum = sum - 10

        # If the dealer busts or is in a position where they would stand, then return a degenerate (simple) vector
        if (sum > 17) or ((sum == 17) and not (dealer_hit_on_soft_17 and soft)):
            return { min(sum, 22) : 1.0 }

        # If we get to this point, we know the dealer will be hitting, so it's time to check their next card
            
        # We know dealer doesn't have BJ, so we need to limit the possibilities for the dealer's second card
        #  (this only applies if the hand has one card)
        if hand == [1] and dealer_cant_start_with_21:
            possibleNextCards = [1,2,3,4,5,6,7,8,9]
        elif hand == [10] and dealer_cant_start_with_21:
            possibleNextCards = [2,3,4,5,6,7,8,9,10,11,12,13]
        else:
            possibleNextCards = [1,2,3,4,5,6,7,8,9,10,11,12,13]

        # Step through the possible next cards and evaluate new hands (current hand + new card) one by one
        for newRank in possibleNextCards:
            # Here is the recursive call
            newOutcomes = Dealer.evaluateDealerHand(hand + [newRank], indent + '  ')
            
            # Now step through the resulting probability vector and merge it into the new vector we're building
            #  (multiply by the conditional probability of the new card)
            for key, value in newOutcomes.items():
                if key in outcomes:
                    outcomes[key] += value / len(possibleNextCards)
                else:
                    outcomes[key] = value / len(possibleNextCards)
    
        if verbose:
            for key in outcomes:
                print(indent + "  " + str(key) + ":" + str(outcomes[key]))

        # Return the final probability vector
        return outcomes

    # Constructor: builds the master mapping of outcomes, a dictionary of probability vectors over outcomes
    # The dict is keyed off of the 1-10 rank of the dealer's up card
    def __init__(self):
        self.dealerOutcomeMap = {}
        for rank in range(1,11):
            self.dealerOutcomeMap[rank] = Dealer.evaluateDealerHand(hand=[rank])

    # Getter for the dealer outcome vector associated with a specific upcard
    def getDealerOutcome(self, dealerUpCard):
        return self.dealerOutcomeMap[min(dealerUpCard,10)]

    # For any given combo of player score and upcard, this method returns the expected payoff
    # +1 = win one unit, -1 = lose one unit, 0 = push
    def getExpectedPayoff(self, dealerUpCard, playerScore, verbose = False):
        if playerScore >21:
            return -1.0
        outcomes = self.getDealerOutcome(dealerUpCard)
        expectedPayoff = 0.0
        for outcome in outcomes:
            if verbose:
                print(str(outcome))

            # player wins
            if (outcome == 22) or (playerScore > outcome):
                expectedPayoff += outcomes[outcome]
                if verbose:
                    print("WIN")
            
            # player loses
            elif outcome > playerScore:
                expectedPayoff -= outcomes[outcome]
                if verbose:
                    print ("LOSE")
        
        return expectedPayoff
    
# Class that holds the player's strategy and decisions
class Player:

    # Expected values for every combination of { player score, soft?, dealer upcard } are stored in these
    #  three dictionaries
    # Example: expectedValueByScoreIfHit[12][False][7] returns the expected value to the player of
    #  taking a hit if their current score is hard 12 when the dealer is showing a 7
    # player scores run 1-21 and dealer upcards are {0,...,10}
    expectedValueByScoreIfHit = {}
    expectedValueByScoreIfStand = {}
    expectedValueByScoreIfDouble = {}

    # Similar the the EV dictionaries above, this one holds the EV for splitting a pair.
    # Dict is keyed by the {1...10} value of each card in the pair
    # Example: expectedValueForPair[3][10] gives the EV of splitting 3s when the dealer is showing a 10,J,Q, or K)
    expectedValueForPair = {}
    
    # This simple dict, again keyed by the pair card, shows the score and soft? value for the associated hand.
    # For example, pairMapToBaseHand[1] returns soft 12 (the player's hand when they have A + A)
    pairMapToBaseHand = {}

    # This method takes a score (e.g. Soft 14) and a dealer upcard and returns 3 KVPs containing EVs for
    #  hitting, standing, or doubling (splitting handled separately)
    # You also need to pass in a reference to the dealer
    # And firstCard is an optional parameter that's used by the split logic. If set to true, it proceeds as if
    #  the player score represents only the first card they've been dealt. It only generates an EV for hitting,
    #  since you would never stand or double on the first card (even if you could).
    def evaluatePlayerHand(self, playerScore, soft, dealerUpCard, dealerPointer, firstCard = False, verbose = False):

        if verbose:
            print("  EVALUATE " + str(playerScore) + " vs dealer's " + str(dealerUpCard))

        # Handles case where we're evaluating a single Ace
        if (playerScore == 1) and firstCard:
            playerScore = 11
            soft = True

        # If a soft hand busts, evaluate it as a hard hand with -10 to the score
        if (playerScore > 21) and soft:
            playerScore -= 10
            soft = False

        # If the player has busted, stop here
        if (playerScore > 21):
            return {'HIT': -1.0, 'STAND': -1.0, 'DOUBLE': -1.0}  

        # If the player stands, the EV is just the expected payoff for their current score given the dealer's upcard
        valueIfStand = dealerPointer.getExpectedPayoff(dealerUpCard, playerScore)

        # Now step through the possible cards that you might get if you were to hit
        valueIfHit = 0.0
        valueIfDouble = 0.0
        possibleNextCards = [1,2,3,4,5,6,7,8,9,10,11,12,13]
        for newRank in possibleNextCards:
            # Calculate the new score, which is slightly complicated due to aces
            newScore = playerScore + (min(newRank,10) if (soft or newRank > 1) else 11)
            newSoft = soft or (newRank == 1)
            if (newScore > 21) and newSoft:
                newScore -= 10
                newSoft = False

            # Now calculate the expected value to hit and double. Note that if firstCard is True then we evaluate
            #  the expected value of the new hand including the possibility of doubling on the next turn.
            # ONE KNOWN ISSUE: we don't consider the possibility of resplitting after the first split (which is
            #  often not even legal, depending on the table)
            valueIfHit += (1/len(possibleNextCards)) * self.getExpectedValue(newScore, newSoft, dealerUpCard, 
                                    (firstCard and allow_double_after_split))

            # Note that the valueIfDouble variable is different, it's evaluating if you double on THIS turn and
            #  get dealt this new card (newRank)
            valueIfDouble += (2/len(possibleNextCards)) * dealerPointer.getExpectedPayoff(dealerUpCard, newScore)
   
        if verbose:
            print ("  EV to HIT : " + str(valueIfHit))
            print ("  EV to STD : " + str(valueIfStand))
            print ("  EV to DBL : " + str(valueIfDouble)) 
            
        return {'HIT': valueIfHit, 'STAND': valueIfStand, 'DOUBLE': valueIfDouble }

    # This method returns the EV of splitting pairs, given a pair card (e.g. 1 if we're talking about a pair of Aces)
    #  and the dealer's up card
    def expectedValueOfSplittingPair(self, pairCard, dealerUpCard, dealerPointer, verbose = False):
        if verbose:
            print("  EVALUATE PAIR OF " + str(pairCard) + " vs dealer's " + str(dealerUpCard))

        # This call calculates the EV of the split
        evSplit = 2.0 * self.evaluatePlayerHand(pairCard, pairCard == 1, dealerUpCard, dealerPointer, True)['HIT']
   
        if verbose:
            print ("  EV to SPLIT : " + str(evSplit))
            
        return evSplit

    # Returns the expected value to the player of a specific score (hard or soft) given the dealer's up card
    # If doubleAllowed is set to True, then the EV includes the value of doubling. This may or may not be
    #  allowed, given the situation.
    def getExpectedValue(self, playerScore, soft, dealerUpCard, doubleAllowed = False):
        if playerScore > 21:
            return -1.0
        
        evHit = self.expectedValueByScoreIfHit[playerScore]['SOFT' if soft else 'HARD'][dealerUpCard]
        evStand = self.expectedValueByScoreIfStand[playerScore]['SOFT' if soft else 'HARD'][dealerUpCard]
        evDouble = self.expectedValueByScoreIfDouble[playerScore]['SOFT' if soft else 'HARD'][dealerUpCard]
        if doubleAllowed:
            return max(evHit, evStand, evDouble)
        else:
            return max(evHit, evStand)

    # This is a setter method that calculates and stores the necessary EVs in the three main EV dicts
    def setExpectedValue(self, playerScore, soft, dealerUpCard):
        choices = self.evaluatePlayerHand(playerScore,soft,dealerUpCard,dealer)
        softString = 'SOFT' if soft else 'HARD'

        # If the dicts haven't been initialized for this player score, do that now
        if not playerScore in self.expectedValueByScoreIfHit.keys():
            self.expectedValueByScoreIfHit[playerScore] = { 'HARD' : {}, 'SOFT' : {}}
            self.expectedValueByScoreIfStand[playerScore] = { 'HARD' : {}, 'SOFT' : {}}
            self.expectedValueByScoreIfDouble[playerScore] = { 'HARD' : {}, 'SOFT' : {}}
        
        # Store the three values in the three dicts in the appropriate place
        self.expectedValueByScoreIfHit[playerScore][softString][dealerUpCard] = choices['HIT']
        self.expectedValueByScoreIfStand[playerScore][softString][dealerUpCard] = choices['STAND']
        self.expectedValueByScoreIfDouble[playerScore][softString][dealerUpCard] = choices['DOUBLE']

    # Print out a strategy table showing what to do for each combo of starting cards and dealer's up card
    # Set showDuoble to False if you only want to show Hit and Stand.
    def printStrategy(self, soft, showDouble = True, showDiff = True):
        print ("OPTIMAL STRATEGY, " + ("SOFT" if soft else "HARD"))
        printString = "      2  3  4  5  6  7  8  9  10 A"
        if showDiff:
            printString += "     " + printString
        print(printString)
        printString = "     =============================="
        if showDiff:
            printString += "    " + printString
        print(printString)
        for playerScore in range (21,12 if soft else 4,-1):
            printString1 = ""
            if playerScore < 10:
                printString1 += " "
            printString1 += str(playerScore) + " : "
            printString2 = printString1
            for x in range(10):
                dealerUpCard = x+2 if x < 9 else 1
                evHit = self.expectedValueByScoreIfHit[playerScore]['SOFT' if soft else 'HARD'][dealerUpCard]
                evStand = self.expectedValueByScoreIfStand[playerScore]['SOFT' if soft else 'HARD'][dealerUpCard]
                evDouble = self.expectedValueByScoreIfDouble[playerScore]['SOFT' if soft else 'HARD'][dealerUpCard]

                evStack = [evHit,evStand]
                if showDouble:
                    evStack.append(evDouble)
                evStack.sort(reverse=True)
                diff = evStack[0] - evStack[1]
                
                if showDouble and (evDouble > evHit) and (evDouble > evStand) and not (soft and playerScore < 12):
                    printString1 += "\033[34m D \033[0m"
                elif evHit > evStand:
                    printString1 += "\033[92m H \033[0m"
                else:
                    printString1 += "\033[31m S \033[0m"   

                if max(evStack) > 0.01:
                    printString2 += "\033[92m"
                elif max(evStack) > -0.01:
                    printString2 += "\033[0m"
                else:
                    printString2 += "\033[31m"

                if diff > 0.5:
                    printString2 += " # \033[0m"
                elif diff > 0.1:
                    printString2 += " + \033[0m"
                else:
                    printString2 += " . \033[0m"

            if showDiff:
                printString1 += "    " + printString2
            print(printString1)
        print("")

    # This shows the table for when to split pairs ('+' sign) and what to do if you don't split
    def printPairStrategy(self, showDouble = False, showDiff = True):
        print ("OPTIMAL STRATEGY FOR PAIRS")
        printString = "      2  3  4  5  6  7  8  9  10 A"
        if showDiff:
            printString += "     " + printString
        print(printString)
        printString = "     =============================="
        if showDiff:
            printString += "    " + printString
        print(printString)
        
        for pairCard in range (10,0,-1):
            printString1 = ""
            if pairCard < 10:
                printString1 += " "
            printString1 += (str(pairCard) if pairCard > 1 else 'A') + " : "
            printString2 = printString1
            for x in range(10):
                dealerUpCard = x+2 if x < 9 else 1
                baseScore = self.pairMapToBaseHand[pairCard]['SCORE']
                baseSoft = self.pairMapToBaseHand[pairCard]['SOFT']
                evHit = self.expectedValueByScoreIfHit[baseScore]['SOFT' if baseSoft else 'HARD'][dealerUpCard]
                evStand = self.expectedValueByScoreIfStand[baseScore]['SOFT' if baseSoft else 'HARD'][dealerUpCard]
                evDouble = self.expectedValueByScoreIfDouble[baseScore]['SOFT' if baseSoft else 'HARD'][dealerUpCard]
                evSplit = self.expectedValueForPair[pairCard][dealerUpCard]

                evStack = [evHit,evStand,evSplit]
                if showDouble:
                    evStack.append(evDouble)
                evStack.sort(reverse=True)
                diff = evStack[0] - evStack[1]
                
                if evHit > evStand:
                    if showDouble and (evDouble > evHit) and (evDouble > evSplit) and not (baseSoft and baseScore < 12):
                        printString1 += "\033[34m D \033[0m"
                    elif (evSplit > evHit):
                        printString1 += "\033[35m + \033[0m"
                    else:
                        printString1 += "\033[92m H \033[0m"
                elif (evSplit > evStand):
                    printString1 += "\033[35m + \033[0m"
                else:
                    printString1 += "\033[31m S \033[0m"

                # print(str(max(evStack)))
                if max(evStack) > 0.01:
                    printString2 += "\033[92m"
                elif max(evStack) > -0.01:
                    printString2 += "\033[0m"
                else:
                    printString2 += "\033[31m"

                if diff > 0.5:
                    printString2 += " # \033[0m"
                elif diff > 0.1:
                    printString2 += " + \033[0m"
                else:
                    printString2 += " . \033[0m"
                
            if showDiff:
                printString1 += "    " + printString2
            print(printString1)
            
        print("")

    # This is a debug method that shows the difference between hit and stand EVs (so you can see how much
    #  your decision matters). The formatting is wonky, but I didn't bother fixing
    def printStrategyDiff(self, soft):
        print("")
        print("      2  3  4  5  6  7  8  9  10 A")
        print("     ==============================")
        for playerScore in range (21,4,-1):
            printString = ""
            if playerScore < 10:
                printString += " "
            printString += str(playerScore) + " : "
            for dealerUpCard in range(1,11):
                if soft:
                    diff = (self.expectedValueByScoreIfHit[playerScore]['SOFT'][dealerUpCard]
                        - self.expectedValueByScoreIfStand[playerScore]['SOFT'][dealerUpCard])
                    if diff > 0.0:
                        printString += " +" + str(int(diff*100)) + " "
                    else:
                        printString += " " + str(int(diff*100)) + " "
                else:
                    diff = (self.expectedValueByScoreIfHit[playerScore]['HARD'][dealerUpCard]
                        - self.expectedValueByScoreIfStand[playerScore]['HARD'][dealerUpCard])
                    if diff > 0.0:
                        printString += " +" + str(int(diff*100)) + " "
                    else:
                        printString += " " + str(int(diff*100)) + " "                  
            print(printString)

    # Constructor for the Player class. Calculates all of the EVs for various strategies and displays
    #  optimal moves in a set of tables
    def __init__(self, dealer):
        self.dealer = dealer

        # Set up the pairs dicts
        self.pairMapToBaseHand[1] = {'SCORE': 12, 'SOFT': True}
        self.expectedValueForPair[1] = {}
        for pairCard in range(2,11):
            self.expectedValueForPair[pairCard] = {}
            self.pairMapToBaseHand[pairCard] = {'SCORE': pairCard * 2, 'SOFT': False}

        # Loop through all of the possible dealer up cards (can be done in any order)
        for dealerUpCard in range(1,11):
            
            # Set scores for hard 11-21 EVs, working backward
            for playerScore in range (21,10,-1):
                self.setExpectedValue(playerScore, False, dealerUpCard)
            
            # Set scores for soft 11-21 EVs, working backward (note these require the hard 11-21s to be done first)
            for playerScore in range (21,10,-1):
                self.setExpectedValue(playerScore, True, dealerUpCard)

            # Now do hard 1-10, working backward. (These rely on hard + soft 11-21)
            for playerScore in range (10,0,-1):
                self.setExpectedValue(playerScore, False, dealerUpCard)
            
                # ...and finally soft 1-10
            for playerScore in range (10,0,-1):
                self.setExpectedValue(playerScore, True, dealerUpCard)

            # Now do pairs
            for pairCard in range(1,11):
                self.expectedValueForPair[pairCard][dealerUpCard] = self.expectedValueOfSplittingPair(
                    pairCard, dealerUpCard,dealer)

        # Print the strategy tables
        self.printStrategy(False, True)
        self.printStrategy(True, True)
        self.printPairStrategy(True)

# This class isn't used at all but could come in handy for other card games
class Card:
    ranks = ['ace','2', '3', '4', '5', '6', '7', '8', '9', '10', 'jack', 'queen', 'king']
    short_ranks = ['A','2', '3', '4', '5', '6', '7', '8', '9', '10', 'J', 'Q', 'K']
    suits = ['spades', 'clubs', 'hearts', 'diamonds']

    def __init__(self, rank, suit):
        if type(rank) == str:
            self.rank = Card.ranks.index(rank)
        else:
            self.rank = rank
        
        if type(suit) == str:
            self.suit = suit
        else:
            self.suit = Card.suits[suit]
            
        self.value = min(self.rank+1,10)
        
        # print(self.cardStringLong() + " " + str(self.value))

    def getRank(self):
        return self.rank

    def cardStringLong(self):
        return Card.ranks[self.rank] + " of " + self.getSuit()

    def rankStringShort(self):
        return Card.short_rank[self.rank]
    
    def getSuit(self):
        return self.suit

    def getValue(self):
        return self.value

# Also not used
def InitializeShoe(numDecks = 1, numSuits = 4):
    shoe = list()
    for d in range(numDecks):
        for s in range(numSuits):
            for c in range(13):
                shoe.append(Card(c,s))
    return shoe

# deck = InitializeShoe(numSuits=1)
# random.shuffle(deck)
dealer = Dealer()
player = Player(dealer)


