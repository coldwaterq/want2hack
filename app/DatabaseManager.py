import psycopg2
from psycopg2.extras import DictConnection
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT
from flask import g
from passlib.hash import bcrypt
from os import urandom
from base64 import b64encode
import traceback
from datetime import datetime

class DatabaseManager :
    __host = 'localhost'
    __database = 'want2hack'
    __user = 'want2hack'
    __port = None

    def __init__(self, app) :
        print "DatabaseManager initialized..."
        self.app = app

    """ NOTES

    """



    #########################################################################################
    # GET API - Functions for retrieving information from the database
    #########################################################################################
    
    # all leveraging functions have access to the relevant connection (g.conn)
    def connect_func(fn) :
        def decor(*args, **kwargs):
            try :
                conn = g.conn
                sql = conn.cursor()
                return fn(*args, sql=sql, conn=conn, **kwargs)
            except Exception, e :
                print e
                return fn(*args, **kwargs)
        return decor

    @connect_func
    def user_rating(self, sql, conn, rating, challenge_id):
        try:
            sql.execute("""
                Update want2hack.sandbox
                SET voted_difficulty=%s
                WHERE challenge_id=%s AND attacker_id=%s AND complete='t';
                """,[rating,challenge_id,g.user['user_id']])
            conn.commit()
            return True
        except Exception, e:
            self.app.logger.warning('user_rating '+str(e))
            traceback.print_exc()
            conn.rollback()
            return False
    
    @connect_func
    def get_difficulty_estimate(self, sql, conn, challenge_id, version):
        sql.execute("""
            SELECT difficulty_estimate
            FROM want2hack.challenge_edition
            WHERE challenge_id=%s and version=%s;
            """,[challenge_id,version])
        return sql.fetchone()

    @connect_func
    def get_leaders(self, sql, conn, num=None):
        try:
            if(num is None):
                sql.execute("""
                    SELECT u.username, u.attack_points, u.challenge_points
                    FROM want2hack.account u
                    ORDER BY u.attack_points+u.challenge_points DESC, 
                        u.challenge_points DESC,
                        u.attack_points DESC;
                    """,[])
            else:
                sql.execute("""
                    SELECT u.username, u.attack_points, u.challenge_points
                    FROM want2hack.account u
                    ORDER BY u.attack_points+u.challenge_points DESC, 
                        u.challenge_points DESC,
                        u.attack_points DESC
                    LIMIT %s;
                    """,[num])
            users=sql.fetchall()
        except Exception, e:
            self.app.logger.warning('get_leaders '+str(e))
            users=[]
        return users

    @connect_func
    def get_hall_of_fame(self, sql, conn):
        try:
            sql.execute("""
                    SELECT u.username, h.description, h.user_points_received
                    FROM want2hack.hof h
                    LEFT JOIN want2hack.account u
                        ON h.user_id=u.user_id
                    WHERE h.description != 'You found the mithical teapot'
                    ORDER BY h.user_points_received DESC;
                """)
            hof = sql.fetchall()
            return hof
        except Exception, e:
            self.app.logger.warning('get_hall_of_fame '+str(e))
            return None

    @connect_func
    def add_hall_of_fame(self, sql, conn, user_id, description, points):
        sql.execute("""
                SELECT user_id
                FROM want2hack.hof
                WHERE user_id=%s
                    AND description=%s
                    AND user_points_received=%s;
            """,[user_id, description, points])
        if sql.fetchone() is not None:
            return(False)
        sql.execute("""
                INSERT INTO want2hack.hof (user_id, description, user_points_received)
                VALUES(%s,%s, %s);        
            """,[user_id, description, points])
        sql.execute("""
                UPDATE want2hack.account a
                SET attack_points = (COALESCE(
                        (SELECT SUM(user_points_received)
                        FROM want2hack.sandbox
                        WHERE attacker_id= a.user_id
                        and complete='t'),0)
                        +
                        COALESCE((SELECT SUM(h.user_points_received)
                        FROM want2hack.hof h
                        WHERE h.user_id = a.user_id),0)
                    );
                """,[])
        conn.commit()
        return True

    @connect_func
    def update(self, sql, conn, challenge_id,version):
        try:
            sql.execute("""
                UPDATE want2hack.sandbox
                SET version_attacked=%s
                WHERE challenge_id=%s and attacker_id=%s;
                """,[version, challenge_id, g.user['user_id']])
            conn.commit()
        except Exception, e:
            self.app.logger.warning('update '+str(e))
            conn.rollback()
            raise e

    @connect_func
    def publish(self, sql, conn, challenge_id, latest_version, difficulty_estimate):
        try:
            sql.execute("""
                UPDATE want2hack.challenge
                SET latest_published_version=%s, latest_version=%s
                WHERE challenge_id=%s AND owner_id=%s;
                """,[latest_version, latest_version+1 ,challenge_id,g.user['user_id']])
            sql.execute("""
                INSERT INTO want2hack.challenge_edition (challenge_id, version, difficulty_estimate)
                VALUES(%s,%s, %s);            
                """,[challenge_id, latest_version+1, difficulty_estimate])            
            sql.execute("""
                UPDATE want2hack.challenge_edition
                SET published='t'
                WHERE challenge_id=%s AND version=%s;
                """,[challenge_id, latest_version])
            conn.commit()
            return True
        except Exception, e:
            self.app.logger.warning('publish '+str(e))
            conn.rollback()
            return False

    @connect_func
    def challenges_needing_approval(self, sql, conn):
        try:
            sql.execute("""
                SELECT challenge_name, challenge_id, owner_id
                FROM challenge
                WHERE (latest_published_version != latest_approved_version
                    OR (latest_published_version is not NULL and latest_approved_version is NULL))
                AND deleted = 'f';
                """)
            return sql.fetchall()
        except Exception, e:
            self.app.logger.warning('challenge_needing_approval '+str(e))
            return(None)

    @connect_func
    def approve(self, sql, conn, challenge_id, approve=True):
        try:
            if(approve):
                sql.execute("""
                    UPDATE want2hack.challenge
                    SET latest_approved_version=latest_published_version
                    WHERE challenge_id=%s
                    RETURNING latest_approved_version;
                    """,[challenge_id])
                version = sql.fetchone()[0]
                sql.execute("""
                    UPDATE want2hack.challenge_edition
                    SET approved='t'
                    WHERE challenge_id=%s AND version=%s;
                    """,[challenge_id, version])
                conn.commit()
            else:
                sql.execute("""
                    SELECT latest_published_version
                    from want2hack.challenge
                    WHERE challenge_id=%s;
                    """,[challenge_id])
                version = sql.fetchone()[0]
                sql.execute("""
                    UPDATE want2hack.challenge
                    SET latest_published_version=latest_approved_version
                    WHERE challenge_id=%s;
                    """,[challenge_id])
                sql.execute("""
                    UPDATE want2hack.challenge_edition
                    SET published='f'
                    WHERE challenge_id=%s AND version=%s;
                    """,[challenge_id, version])
                conn.commit()
            return True
        except Exception, e:
            self.app.logger.warning('approve '+str(e))
            conn.rollback()
            return False

    @connect_func
    def checkout_challenge(self, sql, conn, user_id, challenge_id, version):
        try:
            sql.execute("""
                INSERT INTO want2hack.sandbox (challenge_id, attacker_id, version_attacked)
                VALUES (%s, %s, %s);
                """,[challenge_id, user_id, version])
            conn.commit()
            return True
        except psycopg2.IntegrityError:
            return True
        except Exception, e:
            self.app.logger.warning('checkout_challenge '+str(e))
            conn.rollback()
            return False

    # provide session for logged in user 
    #     (acts as validation of session token as well)
    # provide username for other user
    @connect_func
    def get_user(self,sql,conn, sesh=None, username=None, user_id=None) :
        user = None
        try :
            # only session provided
            if type(sesh) is str :
                id,token = sesh.split('|')
                sql.execute("SELECT user_id, username, attack_points, challenge_points, email FROM want2hack.account WHERE user_id = %s AND session_token = %s LIMIT 1;", [id,token])
                user = sql.fetchone()
            # only username provided
            elif username is not None :
                sql.execute("SELECT user_id, username, tagline, description, md5(email) as gravatar, Date_created, attack_points, challenge_points, email FROM want2hack.account WHERE username = %s LIMIT 1;", [username])
                user = sql.fetchone()
            # only userid provided
            elif user_id is not None :
                sql.execute("SELECT user_id, username, tagline, description, md5(email) as gravatar, Date_created, attack_points, challenge_points, email FROM want2hack.account WHERE user_id = %s LIMIT 1;", [user_id])
                user = sql.fetchone()
            # return None
            else :
                user=None
        except Exception, e :
            self.app.logger.warning('get_user '+str(e))

        return user


    # provide username & challenge_user_n 
    # provide challenge_id
    @connect_func
    def get_challenge(self,sql,conn, challenge_id=None, admin=False) :
        challenge = None

        try :
            if admin:
                sql.execute("""
                Select *
                from want2hack.challenge
                where challenge_id=%s;
                """, [challenge_id])# ther first version must be approved
            else:
                sql.execute("""
                    Select *
                    from want2hack.challenge
                    where challenge_id=%s 
                    and (owner_id=%s or latest_approved_version IS NOT Null) and not deleted;
                    """, [challenge_id, g.user['user_id']])# ther first version must be approved
            challenge = sql.fetchone()
            return challenge
        except Exception, e :
            self.app.logger.warning('get_challenge '+str(e))
            return None

    # provide user_id for logged in user
    # provide username for other user
    @connect_func
    def get_challenges(self,sql,conn, user_id=None, approved=None) :
        challenges = None

        try :
            approved_and = " AND ce.approved = " + ("'t'" if approved else "'f'") if type(approved) is bool else ''
            if(approved):
                version = " c.latest_approved_version "
            else:
                version = " c.latest_version "

            # user_id provided
            if type(user_id) is int :
                sql.execute("""
                    SELECT c.challenge_id, c.challenge_name, c.description, c.latest_version, c.latest_approved_version, ce.difficulty_estimate, ce.difficulty, ce.approved
                    FROM want2hack.challenge c
                        JOIN want2hack.challenge_edition ce 
                            ON ce.challenge_id = c.challenge_id
                            AND ce.version = """+version+"""
                    WHERE c.owner_id = %s and deleted = 'f'
                    """ + approved_and + """
                    ORDER BY difficulty ASC
                    """, [user_id])

            # all challenges
            else :
                sql.execute("""
                    SELECT c.challenge_id, c.challenge_name, c.description, c.latest_version, c.latest_approved_version, c.owner_id, ce.difficulty_estimate, ce.difficulty, ce.approved
                    FROM want2hack.challenge c
                        JOIN want2hack.challenge_edition ce 
                            ON ce.challenge_id = c.challenge_id
                            AND ce.version = """+version+"""
                    WHERE c.deleted = 'f'
                    """ + approved_and + """
                        ORDER BY difficulty ASC
                    """,[g.user['user_id']])

            challenges = sql.fetchall()    
        except Exception, e :
            self.app.logger.warning('get_challenges '+str(e))

        return challenges

    @connect_func
    def forfeit_challenge(self, sql, conn, challenge_id):
        try:
            sql.execute("""
                DELETE FROM want2hack.sandbox
                WHERE challenge_id=%s 
                    and attacker_id=%s;
                """,[challenge_id, g.user['user_id']])
            conn.commit()
            return(True)
        except Exception, e:
            self.app.logger.warning('forfeit_challenge '+str(e))
            conn.rollback()
            return False

    # provide challenge_id to be deleted
    @connect_func
    def delete_challenge(self, sql, conn, challenge_id):
        try:
            sql.execute("""
                UPDATE want2hack.challenge SET deleted='t' 
                    WHERE challenge_id=%s and owner_id=%s
                """, [challenge_id, g.user['user_id']])
            conn.commit()
            return True
        except Exception, e:
            self.app.logger.warning('delete_challenge '+str(e))
            conn.rollback()
            return False
    
    # provide challenge_id to be updated
    # published for when it gets published
    # name that the challenge should now be
    @connect_func
    def update_challenge(self, sql, conn, challenge_id, name, difficulty, version, description):
        try:
            sql.execute("""
                UPDATE want2hack.challenge SET challenge_name = %s, description = %s
                    WHERE challenge_id=%s and owner_id=%s
                """, [name, description, challenge_id, g.user['user_id']])
            sql.execute("""
                UPDATE want2hack.challenge_edition
                SET difficulty_estimate=%s
                WHERE challenge_id=%s and version=%s;
                """,[difficulty,challenge_id, version])
            conn.commit()
            return True
        except Exception, e:
            self.app.logger.warning('update_challenge '+str(e))
            return False

    # provide challenge_name for what it should be called
    @connect_func
    def new_challenge(self,sql,conn, challenge_name) :
        try :
            flag = self.genkey(124)
            sql.execute("""
                INSERT INTO want2hack.challenge (owner_id, description, flag_seed, challenge_name)
                VALUES (%s,%s,%s,%s) RETURNING challenge_id;
                """, [g.user['user_id'], "", flag, challenge_name])
            challenge_id = sql.fetchone()['challenge_id']
            sql.execute("""
                INSERT INTO want2hack.challenge_edition (challenge_id)
                VALUES (%s)
                """, [str(challenge_id)])
            conn.commit()
            return challenge_id
        except Exception, e :
            self.app.logger.warning('new_challenge '+str(e))
            conn.rollback()
            return False

    # the points need to be fixed still
    @connect_func
    def win(self, sql, conn, challenge_id):
        try:
            diff = self.get_challenge_difficulty(challenge_id=challenge_id)
            sql.execute("""
                UPDATE want2hack.sandbox
                SET complete='t'
                WHERE challenge_id=%s and attacker_id=%s
                RETURNING version_attacked;
                """,[challenge_id, g.user['user_id']])
            version = sql.fetchone()[0]
            sql.execute("""
                UPDATE want2hack.sandbox
                SET user_points_received=%s
                WHERE challenge_id=%s and version_attacked=%s and complete='t';
                """,[diff, challenge_id, version])
            sql.execute("""
                UPDATE want2hack.account a
                SET attack_points = (COALESCE(
                        (SELECT SUM(user_points_received)
                        FROM want2hack.sandbox
                        WHERE attacker_id= a.user_id
                        and complete='t'),0)
                        +
                        COALESCE((SELECT SUM(h.user_points_received)
                        FROM want2hack.hof h
                        WHERE h.user_id = a.user_id),0)
                    );
                """,[])
            sql.execute("""
                UPDATE want2hack.account a
                SET challenge_points = (
                    SELECT SUM(b.difficulty)
                    FROM (
                        SELECT MAX(ce.difficulty) as difficulty
                        FROM challenge_edition ce
                        JOIN (
                            SELECT c1.challenge_id 
                            FROM challenge c1
                            WHERE c1.owner_id = a.user_id
                            AND c1.deleted = 'f'
                        ) 
                        as c3 on c3.challenge_id=ce.challenge_id
                        GROUP BY c3.challenge_id
                    ) as b
                )
                WHERE a.user_id=(
                    SELECT owner_id
                    FROM challenge
                    WHERE challenge_id=%s
                    );
                """,[challenge_id])
            conn.commit()
            return True
        except Exception, e:
            conn.rollback()
            self.app.logger.warning('win '+str(e))
            return False
            
    
    # provide user_id for logged in user
    # provide username for other user
    @connect_func
    def get_attacks(self,sql,conn, user_id=None, completed=None, challenge_id=None) :
        attacks = None

        try :
            completed_and_version = " AND s.complete = " + ("'t'" if completed else "'f'") if type(completed) is bool else ''
            id_include = " AND c.challenge_id=%s" if challenge_id is not None else ""
            # user_id provided
            if type(user_id) is int :
                sql.execute("""
                    SELECT c.challenge_name, c.flag_seed, c.owner_id, c.challenge_id, s.*, ((c.owner_id=%s and c.latest_version = s.version_attacked) or (c.owner_id != %s and c.latest_approved_version = s.version_attacked)) AS is_latest_version 
                    FROM want2hack.sandbox as s
                    JOIN want2hack.challenge as c 
                        ON c.challenge_id = s.challenge_id
                    WHERE s.attacker_id = %s and c.deleted = 'f' """+completed_and_version+id_include+""";
                    """, [user_id, user_id, user_id, challenge_id] if challenge_id is not None else [user_id, user_id, user_id])
    
            # return None
            else :
                raise

            attacks = sql.fetchall()
        except Exception, e :
            self.app.logger.warning('get_attacks '+str(e))
        return attacks

    # provide challenge_id
    @connect_func
    def get_attackers(self,sql,conn, challenge_id) :
        attackers = None

        try :
            if type(challenge_id) is int :
                sql.execute("""
                    SELECT a.username, a.attack_points+a.challenge_points as points, s.version_attacked FROM want2hack.challenge c
                        JOIN want2hack.sandbox s ON s.challenge_id = c.challenge_id
                        JOIN want2hack.account a ON a.user_id = s.attacker_id
                    WHERE s.challenge_id = %s and s.complete='t';
                    """, [challenge_id])

                attackers = sql.fetchall()
        except Exception, e :
            self.app.logger.warning('get_attackers '+str(e))

        return attackers

    # This function will be used in the "complete attack" portion. After each user completes
    # their attack on the challenge, and after they vote, this runs to update the difficulty of the
    # challenge. 
    @connect_func
    def get_challenge_difficulty(self,sql,conn, challenge_id, version=None) :
        
        if version is None :
            sql.execute("""
                SELECT 
                    ((SELECT ce3.difficulty_estimate 
                    FROM want2hack.challenge_edition ce3 
                    WHERE ce3.challenge_id = c1.challenge_id
                    AND ce3.version = c1.latest_approved_version))
                    AS diff_estimate,
                ((SELECT avg(s2.voted_difficulty) FROM want2hack.sandbox s2
                WHERE s2.complete = 't'
                AND s2.challenge_id = c1.challenge_id
                AND s2.version_attacked = c1.latest_approved_version
                AND s2.voted_difficulty is not NULL) * 0.5)
                    +
                    (SELECT 
                        ((SELECT count(*) FROM want2hack.sandbox s4
                        WHERE s4.challenge_id = c1.challenge_id
                        AND s4.version_attacked = c1.latest_approved_version)
                        / 
                        (SELECT count(*)-.01 FROM want2hack.sandbox s4
                        WHERE s4.complete = 't'
                        AND s4.challenge_id = c1.challenge_id
                        AND s4.version_attacked = c1.latest_approved_version)) * 0.2)
                AS difficulty, c1.latest_approved_version
                FROM want2hack.challenge c1
                WHERE c1.challenge_id = %s
                """,[challenge_id])
            answer = sql.fetchone()
            try:
                difficulty = float(answer['difficulty'])+answer['diff_estimate']*.3
            except:
                difficulty = answer['diff_estimate']
            version = answer['latest_approved_version']
        elif type(version) is int :
            sql.execute("""
                SELECT 
                    ((SELECT ce3.difficulty_estimate 
                    FROM want2hack.challenge_edition ce3 
                    WHERE ce3.challenge_id = c1.challenge_id
                    AND ce3.version = %s) )
                    AS diff_estimate,
                ((SELECT avg(s2.voted_difficulty) FROM want2hack.sandbox s2
                WHERE s2.complete = 't'
                AND s2.challenge_id = c1.challenge_id
                AND s2.version_attacked = %s
                AND s2.voted_difficulty is not NULL) * 0.5)
                    +
                    (SELECT 
                        ((SELECT count(*) FROM want2hack.sandbox s4
                        WHERE s4.challenge_id = c1.challenge_id
                        AND s4.version_attacked = %s)
                        / 
                        (SELECT count(*)-.01 FROM want2hack.sandbox s4
                        WHERE s4.complete = 't'
                        AND s4.challenge_id = c1.challenge_id
                        AND s4.version_attacked = %s)) * 0.20)
                AS difficulty
                FROM want2hack.challenge c1
                WHERE c1.challenge_id = %s
                """,[version, version, version, version, challenge_id])
            answer = sql.fetchone()
            try:
                difficulty = float(answer['difficulty'])+answer['diff_estimate']*.3
            except:
                difficulty = answer['diff_estimate']
        else :
            return None
        difficulty = difficulty*10
        sql.execute("""
            UPDATE want2hack.challenge_edition
            SET difficulty=%s
            WHERE challenge_id=%s and version=%s
            """,[difficulty, challenge_id, version])
        conn.commit()
        try :
            return difficulty
        except KeyError, e :
            self.app.logger.warning('get_challenge_difficulty '+str(e))
            return None

    #########################################################################################
    # Login API
    #########################################################################################

    @connect_func
    def user_signup(self,sql,conn, username, email, conf_key) :
        try:
            
            sql.execute("""
                DELETE 
                FROM account 
                WHERE (username=%s OR email=%s) 
                    AND date_created < CURRENT_DATE-1 
                    AND date_last_session IS NULL;
                """, [username, email])
            sql.execute("""
                INSERT INTO want2hack.account (username, email, confirmation)
                VALUES (%s,%s,%s)
                """, [username, email, conf_key])
            conn.commit()
            return {'conf_key':bcrypt.encrypt(str(datetime.now().date())+conf_key)}
        except Exception, e:
            self.app.logger.warning('user_signup '+str(e))
            return None

    @connect_func
    def password_reset(self,sql,conn, username, conf_key) :
        sql.execute("""
            UPDATE want2hack.account
            SET confirmation=%s 
            WHERE username=%s
            RETURNING email;
            """, [conf_key, username])
        user = sql.fetchone()
        if(user is not None):
            user={'email':user['email'],'conf_key':bcrypt.encrypt(str(datetime.now().date())+conf_key)}
        conn.commit()
        return user


    @connect_func
    def user_signout(self,sql,conn, sesh) :
        try :
            if type(sesh) is str :
                query = """
                    UPDATE want2hack.account SET session_token = NULL
                    WHERE session_token = %s
                    RETURNING 't'
                """
                sql.execute(query, [sesh])
                out = sql.fetchone()
                if type(out) is dict :
                    conn.commit()
                    return True
        except Exception, e :
            self.app.logger.warning('user_signout '+str(e))        

        return False

    @connect_func
    def user_signin(self,sql,conn, username, password=None, confirmation=None) :
        skeptical, user = None, None
        skip_validate = False
        try :
            if confirmation is not None:
                query = """
                    SELECT user_id, confirmation FROM want2hack.account
                    WHERE username = %s
                """
                sql.execute(query, [username])
                skeptical = sql.fetchone()
                if(skeptical is None  or skeptical['confirmation'] is None or not bcrypt.verify((str(datetime.now().date())+skeptical['confirmation']),confirmation)):
                    return None
                if password is not None:
                    password = bcrypt.encrypt(password)
                query = """
                    UPDATE want2hack.account SET confirmation = NULL, password=%s WHERE user_id = %s;
                """

                # this breaks if the confirmation was invalid
                # and thus exits try, returning None
                sql.execute(query, [password,skeptical['user_id']])

                conn.commit()
                skip_validate = True
            else :
                query = """
                    SELECT user_id, password FROM want2hack.account 
                    WHERE username = %s;
                """
                sql.execute(query, [username])
                skeptical = sql.fetchone()    

            # skip_validate only ever runs once per use, during their account confirmation
            # ~= one time pad. Not quite equal to a one time pad.
            if (skip_validate or (not skeptical is None and not skeptical['password'] is None and bcrypt.verify(password,skeptical['password']))) :
                sesh = self.genkey(128)
                query = """
                    UPDATE account SET 
                        session_token = %s, 
                        date_last_session = NOW() 
                    WHERE user_id = %s 
                    RETURNING *;
                """
                sql.execute(query, [sesh, skeptical['user_id']])
                user = sql.fetchone()
                user["session_token"] = str(user["user_id"])+"|"+user["session_token"]
                if user is not None :
                    conn.commit()
                else :
                    conn.rollback()

        except Exception, e :
            self.app.logger.warning('user_signin '+str(e))
        return user    


    #########################################################################################
    # Operational functions
    #########################################################################################

    # returns a new connection to the database
    def connect_db(self) :
        try :
            conn = psycopg2.connect(
                host=self.__host, 
                database=self.__database, 
                user=self.__user, 
                password=self.app.config['DB_PASSWORD'], 
                connection_factory = DictConnection
            )
            # gonna try it without this for manual concurrency control
            #conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
        except psycopg2.DatabaseError, e :
            self.app.logger.warning('connect_db '+str(e))
            raise

        return conn

    def genkey(self, n) :
            key = b64encode(urandom(n))
            return key[0:n]
