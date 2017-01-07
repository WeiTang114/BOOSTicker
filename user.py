import os

def load_users(userconf_file):
    # Put all these spaghettis into a class
    d = {}
    if not os.path.exists(userconf_file):
        open(userconf_file, 'w+').close()
        return d

    with open(userconf_file, 'r') as f:
        for l in f:
            if not l.strip():
                continue
            user = load_user(l)
            d[user.uid] = user

    return d

def load_user(line):
    print 'load_user:', line
    items = line.strip().split(',')
    uid, is_group, speed, enabled = items

    is_group = bool(int(is_group))
    speed = float(speed)
    enabled = bool(int(enabled))

    return User(uid, is_group, speed, enabled)

def write_users(users, userconf_file):
    if not isinstance(users, dict):
        raise TypeError('users must be dict {uid: User}')
    
    with open(userconf_file, 'w+') as f:
        for uid, u in users.iteritems():
            print>>f, '%s,%d,%f,%d' % (uid, u.is_group, u.speed, u.enabled)

class User:
    def __init__(self, uid, is_group, speed, enabled):
        self.uid = uid
        self.is_group = bool(int(is_group))
        self.speed = float(speed)
        self.enabled = bool(int(enabled))
