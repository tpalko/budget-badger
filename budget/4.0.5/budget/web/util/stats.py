import math 

#wholes = [1,2,3,5,10,15,20,50,80,85,90,95,97,98,99,100]
wholes = [4,5,6,7,8,10,12,20,30,40,50,60,70,80,90,100]
def nearest_whole(val):
    lastdiff = 101
    choice_w = None 
    for w in wholes:
        diff = abs(w - val)
        if diff < lastdiff:
            lastdiff = diff 
            choice_w = w
    return choice_w

