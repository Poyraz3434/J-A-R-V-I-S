"""Özellik 3 — Arıza akışı state machine testleri (saf, Qt'siz)."""
import unittest

from troubleshoot_flow import (
    FlowState, Solution, TriedEntry, TroubleshootFlow, is_dangerous,
)

SRC = "https://example.com/kaynak"


def make_flow(solutions, verify_results=None, apply_ok=True, research_calls=None):
    """Enjeksiyonlu akış kurar; uygulama/verify çağrıları kayıt altındadır."""

    def research_fn(problem, os_name, mode, exclude):
        if research_calls is not None:
            research_calls.append({"problem": problem, "mode": mode,
                                   "exclude": set(exclude)})
        kept = [s for s in solutions if s.title not in exclude]
        return kept, [SRC]

    applied: list = []

    def apply_fn(solution, os_name):
        applied.append(solution.title)
        return (apply_ok, f"uygulandı: {solution.title}")

    seq = iter(verify_results if verify_results is not None else [True])

    def verify_fn(solution, os_name):
        return next(seq, None)

    flow = TroubleshootFlow("Windows", research_fn, apply_fn, verify_fn)
    return flow, applied


class HappyPathTests(unittest.TestCase):
    def test_research_apply_test_done(self):
        """bekleme → araştırma → uygulama → test(True) → DONE."""
        flow, applied = make_flow([Solution(title="çözüm A", steps=["adım 1"])])
        self.assertIs(flow.state, FlowState.WAITING)
        step = flow.submit("ses yok")
        self.assertIs(step.state, FlowState.APPLYING)
        self.assertIsNotNone(flow.current)
        step = flow.apply_current()
        self.assertIs(step.state, FlowState.TESTING)
        step = flow.run_test()
        self.assertIs(step.state, FlowState.DONE)
        self.assertEqual(applied, ["çözüm A"])
        self.assertEqual(flow.tried[0].result, "ok")

    def test_reset_returns_waiting(self):
        flow, _ = make_flow([Solution(title="A")])
        flow.submit("p")
        flow.apply_current()
        flow.run_test()  # verify True → DONE
        flow.reset()
        self.assertIs(flow.state, FlowState.WAITING)
        self.assertEqual(flow.tried, [])


class UserNoLoopTests(unittest.TestCase):
    """Spec: kullanıcı 'hayır' derse sıradaki alternatif denenir (döngü)."""

    def test_no_loops_until_exhausted(self):
        solutions = [Solution(title="A"), Solution(title="B")]
        flow, applied = make_flow(solutions, verify_results=[None, None])
        flow.submit("p")
        flow.apply_current()
        step = flow.run_test()  # otomatik test yetersiz → manuel sor
        self.assertIs(step.state, FlowState.CONFIRMING)
        step = flow.user_verdict(False)  # kullanıcı: hayır
        self.assertIs(step.state, FlowState.APPLYING)
        self.assertEqual(flow.current.title, "B")
        flow.apply_current()
        step = flow.run_test()
        self.assertIs(step.state, FlowState.CONFIRMING)
        step = flow.user_verdict(False)  # tekrar hayır → tükendi
        self.assertIs(step.state, FlowState.EXHAUSTED)
        self.assertEqual(applied, ["A", "B"])       # tekrar denenmedi
        self.assertEqual([t.result for t in flow.tried], ["failed", "failed"])

    def test_user_yes_closes(self):
        flow, _ = make_flow([Solution(title="A")], verify_results=[None])
        flow.submit("p")
        flow.apply_current()
        flow.run_test()
        step = flow.user_verdict(True)
        self.assertIs(step.state, FlowState.DONE)

    def test_verify_false_moves_to_next(self):
        flow, _ = make_flow(
            [Solution(title="A"), Solution(title="B")], verify_results=[False])
        flow.submit("p")
        flow.apply_current()
        step = flow.run_test()  # otomatik test: çözülmedi
        self.assertIs(step.state, FlowState.APPLYING)
        self.assertEqual(flow.current.title, "B")
        self.assertEqual(flow.tried[0].result, "failed")


class ExhaustedEdgeTests(unittest.TestCase):
    def test_empty_research_exhausted_with_manual_and_links(self):
        """Araştırma sonuçsuz → EXHAUSTED + manuel öneri."""
        flow, _ = make_flow([])
        step = flow.submit("bilinmeyen hata")
        self.assertIs(step.state, FlowState.EXHAUSTED)
        self.assertIn("Alternatif", step.message)
        self.assertIn("Manuel", step.message)

    def test_exhausted_message_lists_tried_and_resources(self):
        """Tükenince: denenenler listesi + kaynak linkleri görünür."""
        solutions = [Solution(title="A"), Solution(title="B")]
        flow, _ = make_flow(solutions, verify_results=[False, False])
        flow.submit("p")
        flow.apply_current()
        flow.run_test()    # False → B sıradaki
        flow.apply_current()
        step = flow.run_test()  # False → tükendi
        self.assertIs(step.state, FlowState.EXHAUSTED)
        self.assertIn("Denenenler", step.message)
        self.assertIn("A (başarısız)", step.message)
        self.assertIn(SRC, step.message)

    def test_research_receives_tried_exclude(self):
        """Yeni research çağrısında denenmiş başlıklar exclude edilir."""
        calls = []
        flow, _ = make_flow([Solution(title="A")], research_calls=calls)
        flow.tried.append(TriedEntry("Eski Çözüm", "failed"))
        flow.submit("p")
        self.assertIn("Eski Çözüm", calls[0]["exclude"])


class DangerApprovalTests(unittest.TestCase):
    """Spec: zararlı işlemden ÖNCE ekstra onay."""

    def test_danger_blocks_apply_until_approved(self):
        sol = Solution(title="Disk bölümleme",
                       steps=["diskpart ile diski temizle"])
        flow, applied = make_flow([sol, Solution(title="B")])
        step = flow.submit("p")
        self.assertIs(step.state, FlowState.APPLYING)
        self.assertTrue(flow.pending_danger)
        self.assertEqual(applied, [], "onaysız uygulama yapılmamalı")
        step = flow.approve_danger(True)
        self.assertFalse(flow.pending_danger)
        self.assertIs(step.state, FlowState.APPLYING)
        flow.apply_current()
        self.assertEqual(applied, ["Disk bölümleme"])

    def test_danger_rejected_skips_to_next(self):
        sol = Solution(title="Zararlı", steps=["format c:"], dangerous=True)
        flow, applied = make_flow([sol, Solution(title="B")])
        flow.submit("p")
        self.assertTrue(flow.pending_danger)
        step = flow.approve_danger(False)
        self.assertIs(step.state, FlowState.APPLYING)
        self.assertEqual(flow.current.title, "B")
        self.assertEqual(flow.tried[0].result, "skipped")
        self.assertEqual(applied, [])

    def test_is_dangerous_patterns(self):
        self.assertTrue(is_dangerous("diskpart ile diski temizle"))
        self.assertTrue(is_dangerous("system32 dosyalarını sil"))
        self.assertFalse(is_dangerous("geçici dosyaları temizle"))


if __name__ == "__main__":
    unittest.main()
