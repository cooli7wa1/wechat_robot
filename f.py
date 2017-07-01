class animal:
    def eat(self):
        print 'eat...'

class cat(animal):
    def drink_milk(self):
        self.eat()
        print 'drink milk'

aa = cat()
aa.drink_milk()
