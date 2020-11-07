class User():
    def __init__(self, username, password, uid=None):
        self.username=username
        self.password=password
        self.uid=uid

    def is_active(self):
        return True
    
    def get_id(self):
        if self.uid:
            return str(self.uid)
        return str(self.username)
    
    def is_authenticated(self):
        return True