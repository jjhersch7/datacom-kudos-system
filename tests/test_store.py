"""Unit tests for Kudos store and its moderation rules."""
import tempfile
import unittest
from pathlib import Path
from store import Store, Problem


class KudosTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.db=Store(Path(self.tmp.name)/'kudos.db')
        self.alex=1;self.jamie=2;self.admin=3

    def tearDown(self):
        self.tmp.cleanup()

    def test_login_and_password(self):
        token, person=self.db.authenticate('alex@example.test','DemoPass123!')
        self.assertEqual(person['role'],'employee')
        self.assertEqual(self.db.current_user(token)['id'],self.alex)
        self.db.logout(token)
        self.assertIsNone(self.db.current_user(token))
        with self.assertRaises(Problem) as err:
            self.db.authenticate('alex@example.test','wrong')
        self.assertEqual(err.exception.code,401)

    def test_list_excludes_self(self):
        colleagues=self.db.colleagues(self.alex)
        self.assertNotIn(self.alex,[c['id'] for c in colleagues])
        self.assertEqual(len(colleagues),2)

    def test_create_and_feed(self):
        id_=self.db.create_kudos(self.alex,self.jamie,'Great work!')
        feed=self.db.feed()
        self.assertEqual(feed[0]['id'],id_)
        self.assertEqual(feed[0]['message'],'Great work!')
        self.assertEqual(feed[0]['is_visible'],1)

    def test_invalid_messages_and_recipients(self):
        for recipient,message in [(self.alex,'Hello'),(self.jamie,''),(self.jamie,'x'*501),(99,'Nice')]:
            with self.subTest(recipient=recipient, message=message[:6]):
                with self.assertRaises(Problem) as err:
                    self.db.create_kudos(self.alex,recipient,message)
                self.assertEqual(err.exception.code,400)

    def test_duplicates(self):
        self.db.create_kudos(self.alex,self.jamie,'Thanks')
        with self.assertRaises(Problem) as err:
            self.db.create_kudos(self.alex,self.jamie,'Thanks')
        self.assertEqual(err.exception.code,409)

    def test_rate_limit(self):
        for i in range(5):
            self.db.create_kudos(self.alex,self.jamie,f'Appreciation {i}')
        with self.assertRaises(Problem) as err:
            self.db.create_kudos(self.alex,self.jamie,'One more')
        self.assertEqual(err.exception.code,429)

    def test_moderation_hide_restore_delete(self):
        k=self.db.create_kudos(self.alex,self.jamie,'Test moderation')
        self.db.moderate(self.admin,k,False,'Inappropriate')
        self.assertEqual(len(self.db.feed()),0)
        admin=self.db.feed(admin=True)
        self.assertEqual(admin[0]['reason_for_moderation'],'Inappropriate')
        self.assertIsNotNone(admin[0]['moderated_at'])
        self.db.moderate(self.admin,k,True,'Reviewed')
        self.assertEqual(len(self.db.feed()),1)
        self.db.delete(k)
        self.assertEqual(len(self.db.feed(admin=True)),0)

    def test_invalid_moderation(self):
        with self.assertRaises(Problem):
            self.db.moderate(self.admin,999,False)
        with self.assertRaises(Problem):
            self.db.moderate(self.admin,1,'false')

    def test_feed_pagination_validation(self):
        with self.assertRaises(Problem):
            self.db.feed(0)
        self.assertEqual(self.db.feed(2),[])


if __name__=='__main__':
    unittest.main()
