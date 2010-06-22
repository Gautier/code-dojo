#!/usr/bin/python
from cmd import Cmd
import SocketServer
import re
import sys
try:
    from reverend.thomas import Bayes
except ImportError:
    Bayes = None

DIRECTIONS = 'N', 'E', 'S', 'W'
NORTH, EAST, SOUTH, WEST = DIRECTIONS

all_item_names = {}

class Player(object):
    def __init__(self, location, name='Player'):
        assert isinstance(location, Location)
        self.location = location
        self.name = name
        self.items = {}

    def inventory(self):
        if not self.items:
            return "Your hands are empty!"
        return "You are carrying: " + ", ".join(self.items)
    

class Location(object):
    def __init__(self, name, description=""):
        self.name = name
        self.description = description 
        self.exits = {}
        self.items = {}
    
    def __str__(self):
        return self.name

    def add_direction(self, direction, other_location):
        assert direction in DIRECTIONS
        self.exits[direction] = other_location   
    
    def describe(self):
        out = ''
        out += "Current location: %s\n%s\n" % (self.name, self.description)
        out += "You can see: "
        out += ", ".join(item.name
            for item in self.items.itervalues() if not item.hidden)
        out += "\n"
        for direction, location in self.exits.iteritems():
            out += "\t%s (%s)\n" % (location, direction)
        return out


class Item(object):
    def __init__(self, name, description="", location=None):
      self.name = name
      self.description = description
      self.location = location
      self.aliases = []
      self.fixed = False
      self.hidden = False

    def __str__(self):
      return self.name

    def add_aliases(self, aliases):
      self.aliases.extend(aliases)

    def describe(self):
      return self.description



sample_universe = """
:Garage
You are in the garage. There are no cars here currently.
E:Bedroom
W:Kitchen

:Kitchen
The kitchen is immaculate. You suspect that nobody has ever actually prepared any food here.
E:Garage

"""

def test_location():
    startroot = Location('Start room')
    kitchen = Location('Kitchen')
    startroot.add_direction(NORTH, kitchen)
    
def test_player():
    lobby = Location('Lobby')
    john = Player(lobby, 'John')


def find_item(items, name):
    name = name.lower()
    for item in items.itervalues():
	if name == item.name.lower() or name in item.aliases:
	   return item
    return None


def load_universe(content):
    location = first_location = None
    item = None
    locations = {}
    items = {}

    for line in content:
        line = line.strip()
        if not line or line.startswith('#'):
            continue

        if line.startswith(':'):
            item = None
            location = Location(line[1:])
            locations[line[1:]] = location
            if not first_location:
                first_location = location
        elif line.startswith('*'):
            location = None
            item = Item(line[1:])
            items[line[1:]] = item
        elif location is not None and not location.description:
            location.description = line
        elif location is not None:
            direction, destination = line.split(':', 1)
            location.add_direction(direction, destination)
        elif item is not None and not item.location and not item.description:
            item.location = line
        elif item is not None and not item.description:
            item.description = line
        elif item is not None:
            cmd, arg = line.split(':', 1)
            if cmd == 'A':
              item.add_aliases(s.strip().lower() for s in arg.split(','))
            elif cmd == "F":
              item.fixed = arg
            elif cmd == "H":
              item.hidden = True

    for location in locations.itervalues():
       for direction, destination in location.exits.items():
           try:
               location.add_direction(direction, locations[destination])
           except KeyError:
               raise SystemError("Your universe file sucks! %s" % destination)

    for item in items.itervalues():
        location = locations[item.location]
        location.items[item.name] = item
        
        all_item_names[item.name] = item.name
        for alias in item.aliases:
            all_item_names[alias] = item.name
            
            
    return locations, first_location

            
class Game(Cmd):

    def __init__(self, gamefile, player_name,
                    stdin=sys.stdin, stdout=sys.stdout):
        Cmd.__init__(self, stdin=stdin, stdout=stdout)
        self.stdout = stdout

        self.locations, self.start_room = load_universe(file(gamefile))
        self.player = Player(self.start_room, player_name)

        self.guesser = self._load_guesser()
        if self.guesser is not None:
            # check that you can guess that 'grab' aliases to 'take'
            assert self.guesser.guess('grab')

        self.display(self.player.location.describe())

    def _load_guesser(self):
        if Bayes is None:
            return None
        guesser = Bayes()
        self.display(guesser)
        self.display(dir(guesser))
        guesser.load('commands.bays')
        return guesser

    def do_move(self, direction):
        direction = direction.upper()
       
        newroom = self.player.location.exits.get(direction,None)
        if newroom == None:
            self.display("No pass around!")
            return
        
        self.player.location = self.player.location.exits[direction]
        self.display(self.player.location.describe())

    def do_go(self, direction):
        return self.do_move(direction)

    def do_look(self, where):
        if where == "":
            self.display(self.player.location.describe())
        else:
            # TODO validate where
            target = self.player.location.exits.get(where.upper())
            if target:
                self.display(target.describe())
                return
            item = find_item(self.player.location.items, where)
            if not item:
                item = find_item(self.player.items, where)
            if item:
                self.display(item.describe())
            else:
                self.display("You can't see", where)

    def do_examine(self, where):
        return self.do_look(where)
            
    def do_ex(self, where):
        return self.do_look(where)

    def do_get(self, target):
        item = find_item(self.player.location.items, target)
        if item:
            if item.fixed:
                self.display(item.fixed)
                return
            del self.player.location.items[item.name]
            self.player.items[item.name] = item
            self.display("Taken ", item.name)
        else:
            self.display("You can't see ", target)

    def do_take(self, target):
        return self.do_get(target)
            
    def do_drop(self, target):
        item = find_item(self.player.items, target)
        if item:
            del self.player.items[item.name]
            self.player.location.items[item.name] = item
            self.display("Dropped ", item.name)
        else:
            self.display("You don't have ", target)

    def do_inventory(self, target):
        self.display(self.player.inventory())

    def do_inv(self, target):
        return self.do_inventory(target)

    def do_i(self, target):
        return self.do_inventory(target)

    def do_put(self, target):
        return self.do_drop(target)

    def do_quit(self, target):
        print self.player.name, " just left"
        self.display("Bye ", self.player.name)
        # returning True from one of the command terminates the Cmd.cmdloop()
        return True
            
    def postcmd(self, stop, x):
        return stop
    
    def default(self, line):
        # failed all the above, 
        if self.guesser is not None:
            # let's use Bayes
            all_item_names['north'] = 'N'
            all_item_names['east'] = 'E'
            all_item_names['west'] = 'W'
            all_item_names['south'] = 'S'
            all_item_names['N'] = 'N'
            all_item_names['E'] = 'E'
            all_item_names['W'] = 'W'
            all_item_names['S'] = 'S'
            for name in all_item_names:
                if re.search(r'\b%s\b' % re.escape(name), line, re.I):
                    guesses = self.guesser.guess(line.replace(name,''))
                    self.display(guesses)
                    if guesses:
                        method_name = guesses[0][0]
                        getattr(self, method_name)(all_item_names[name])
                        return

    def display(self, *args):
        message = "".join(args)
        self.stdout.write(message)

def play(gamefile):
    #start_room = _create_universe()
    
    player_name = raw_input('Player name?: ') or 'No name'
    g = Game(gamefile, player_name)    
    
    g.cmdloop()


class TelnetGame(SocketServer.StreamRequestHandler):
    def handle(self):
        self.wfile.write("Player name?: ")
        player_name = self.rfile.readline()
        player_name = player_name.replace("\r\n", "")
        player_name = "No name" if not player_name else player_name

        print "handling request from ", player_name, "@", self.client_address
        g = Game(TelnetGame.gamefile, player_name, self.rfile, self.wfile)
        g.cmdloop()

class ThreadedTCPServer(SocketServer.ThreadingMixIn, SocketServer.TCPServer):
    pass

def main():
    if len(sys.argv) < 2:
        print "usage: adventure.py command gamefile [command specific options]"
        print "Where command can be"
        print "    * test : 'unit' tests"
        print "    * server : internet adventure game server"
        print "    * local : local play"

    command, gamefile = sys.argv[1].lower(), sys.argv[2]
    if command == 'test':
        test_location()
        test_player()

    elif command == 'server':
        if len(sys.argv) != 5:
            print "usage: adventure.py server gamefile host port"
            print "     example: adventure.py server data.txt localhost 2300"
            return

        TelnetGame.gamefile = gamefile

        host, port = sys.argv[3], sys.argv[4]
        port = int(port)

        Game.use_rawinput = False
        server = ThreadedTCPServer((host, port), TelnetGame)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            # clean socket
            server.server_close()

    elif command == "local":
        try:
            play(gamefile)
        except KeyboardInterrupt:
            pass

if __name__ == '__main__':
    main()
