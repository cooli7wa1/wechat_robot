class aa:
    a = 0
    def get_a(self):
        print self.a

aa.a = 1
aa().get_a()
