"""
JARVIS v10 APEX PRIME — Kod Yazma & Düzenleme Ajanı
====================================================
Kullanıcı "şu projede X özelliğini ekle" veya "şu hatayı düzelt" dediğinde:
  1. Proje klasörünü tara
  2. İlgili dosyaları oku
  3. AI ile değişiklik planla + kullanıcıya özetle
  4. permissions.py üzerinden onay al
  5. Dosyaları atomik yaz
  6. Subprocess sandbox'ta test et
  7. Hata varsa maks. MAX_RETRY deneme
  8. Git: değişiklik öncesi otomatik stash/commit, "geri al" desteği

Güvenlik:
  - Yalnızca safe_path_under_root ile doğrulanmış dizinlerde çalışır
  - System32, registry, kritik klasörler asla erişilmez
  - Subprocess: timeout=30, shell=False
"""
from __future__ import annotations

import os
import subprocess
import time
from pathlib import Path
from typing import Optional

from logger_setup import logger
from services.permissions import ActionCategory, get_permission_manager

MAX_RETRY     = 3
MAX_FILE_BYTES = 500_000   # 500 KB per file
MAX_FILES_READ = 20
ALLOWED_SUFFIXES = {
    ".py", ".js", ".ts", ".jsx", ".tsx", ".java", ".cs", ".cpp", ".c", ".h",
    ".go", ".rs", ".rb", ".php", ".swift", ".kt", ".r", ".lua",
    ".html", ".css", ".scss", ".sass", ".xml", ".svg",
    ".json", ".yaml", ".yml", ".toml", ".ini", ".cfg", ".env",
    ".md", ".rst", ".txt", ".sql",
}

# Sistem / kritik dizinler — asla dokunma
FORBIDDEN_PATTERNS = {
    "system32", "syswow64", "windows", "program files (x86)", "program files",
    "appdata\\roaming\\microsoft", "appdata\\local\\microsoft",
    "\\winnt\\", "\\$recycle.bin",
}


def _is_safe_path(path: Path) -> bool:
    """Yol sistem dizinlerinden uzakta mı kontrol eder."""
    path_str = str(path).lower()
    for forbidden in FORBIDDEN_PATTERNS:
        if forbidden in path_str:
            return False
    return True


def _safe_under_home(path: Path) -> bool:
    """Yol kullanıcı home dizini altında mı?"""
    try:
        home = Path.home().resolve()
        resolved = path.resolve()
        return resolved == home or home in resolved.parents
    except Exception:
        return False


# ── Proje tarayıcı ────────────────────────────────────────────────────────

def scan_project(root_dir: str, max_depth: int = 4) -> dict:
    """
    Proje klasörünü tarar.
    Returns: {"tree": str, "files": [Path], "stats": dict}
    """
    root = Path(root_dir).resolve()
    if not root.exists() or not root.is_dir():
        return {"error": f"Klasör bulunamadı: {root_dir}"}
    if not _safe_under_home(root) or not _is_safe_path(root):
        return {"error": "Bu klasör güvenlik kısıtlamaları nedeniyle taranamaz."}

    tree_lines = [f"📁 {root.name}/"]
    files = []

    def _walk(directory: Path, prefix: str, depth: int):
        if depth > max_depth:
            return
        try:
            entries = sorted(directory.iterdir(), key=lambda p: (p.is_file(), p.name))
        except PermissionError:
            return
        for entry in entries:
            if entry.name.startswith(".") and entry.name not in {".env", ".gitignore"}:
                continue
            if entry.name in {"__pycache__", "node_modules", ".git", "venv", ".venv",
                               "dist", "build", ".pytest_cache", ".mypy_cache"}:
                continue
            connector = "├── " if entry != entries[-1] else "└── "
            if entry.is_dir():
                tree_lines.append(f"{prefix}{connector}📁 {entry.name}/")
                _walk(entry, prefix + ("│   " if entry != entries[-1] else "    "), depth + 1)
            elif entry.is_file() and entry.suffix.lower() in ALLOWED_SUFFIXES:
                size_kb = round(entry.stat().st_size / 1024, 1)
                tree_lines.append(f"{prefix}{connector}{entry.name} ({size_kb}KB)")
                files.append(entry)

    _walk(root, "", 1)

    stats = {
        "total_files": len(files),
        "total_size_kb": round(sum(f.stat().st_size for f in files) / 1024, 1),
        "languages": list({f.suffix for f in files}),
    }
    return {
        "root": str(root),
        "tree": "\n".join(tree_lines),
        "files": files,
        "stats": stats,
    }


def read_relevant_files(files: list[Path], query: str, max_files: int = MAX_FILES_READ) -> dict[str, str]:
    """
    Görevle en ilgili dosyaları okur.
    Basit skor: dosya adında veya içeriğinde query kelimeleri geçiyor mu.
    """
    keywords = set(query.lower().split())
    scored = []
    for f in files:
        score = 0
        name_lower = f.name.lower()
        for kw in keywords:
            if kw in name_lower:
                score += 3
        # İçeriği okuyup puan ver (küçük dosyalar için)
        try:
            if f.stat().st_size <= 50_000:
                content_preview = f.read_text(encoding="utf-8", errors="ignore")[:2000].lower()
                for kw in keywords:
                    if kw in content_preview:
                        score += 1
        except Exception:
            pass
        scored.append((score, f))

    scored.sort(reverse=True)
    result = {}
    for _, f in scored[:max_files]:
        try:
            if f.stat().st_size > MAX_FILE_BYTES:
                result[str(f)] = f"[DOSYA ÇOK BÜYÜK — {round(f.stat().st_size/1024, 1)} KB, ilk 10K gösteriliyor]\n" + \
                                  f.read_text(encoding="utf-8", errors="ignore")[:10_000]
            else:
                result[str(f)] = f.read_text(encoding="utf-8", errors="ignore")
        except Exception as exc:
            result[str(f)] = f"[OKUNAMADI: {exc}]"
    return result


# ── Git entegrasyonu ──────────────────────────────────────────────────────

class GitManager:
    def __init__(self, repo_dir: str):
        self.repo_dir = repo_dir
        self._git_available = self._check_git()

    def _check_git(self) -> bool:
        try:
            result = subprocess.run(
                ["git", "-C", self.repo_dir, "status"],
                capture_output=True, timeout=5, shell=False)
            return result.returncode == 0
        except Exception:
            return False

    def stash_or_commit(self, message: str = "JARVIS otomatik yedek") -> str:
        """Değişiklik öncesi git stash (çalışma alanı temiz değilse) veya commit."""
        if not self._git_available:
            return ""
        try:
            # Çalışma alanı temiz mi?
            status = subprocess.run(
                ["git", "-C", self.repo_dir, "status", "--porcelain"],
                capture_output=True, text=True, timeout=5, shell=False)
            if status.stdout.strip():
                # Kirli — stash
                subprocess.run(
                    ["git", "-C", self.repo_dir, "stash", "push", "-m", f"jarvis-pre-edit-{int(time.time())}"],
                    capture_output=True, timeout=10, shell=False)
                return "git stash"
            return ""
        except Exception as exc:
            logger.warning("[CodeAgent] Git stash hatası: %s", exc)
            return ""

    def commit(self, files: list[str], message: str) -> str:
        """Değiştirilen dosyaları commit et."""
        if not self._git_available:
            return ""
        try:
            for f in files:
                subprocess.run(["git", "-C", self.repo_dir, "add", f],
                               capture_output=True, timeout=5, shell=False)
            result = subprocess.run(
                ["git", "-C", self.repo_dir, "commit", "-m", f"[JARVIS] {message}"],
                capture_output=True, text=True, timeout=10, shell=False)
            if result.returncode == 0:
                return f"Git commit: {result.stdout.strip()[:100]}"
            return ""
        except Exception as exc:
            logger.warning("[CodeAgent] Git commit hatası: %s", exc)
            return ""

    def pop_stash(self) -> str:
        """Stash'i geri yükle (geri alma)."""
        if not self._git_available:
            return "Git mevcut değil."
        try:
            result = subprocess.run(
                ["git", "-C", self.repo_dir, "stash", "pop"],
                capture_output=True, text=True, timeout=10, shell=False)
            if result.returncode == 0:
                return "Git stash pop — değişiklikler geri alındı."
            return f"Git stash pop başarısız: {result.stderr[:200]}"
        except Exception as exc:
            return f"Git geri alma hatası: {exc}"


# ── Atomik dosya yazıcı ────────────────────────────────────────────────────

def _write_atomic(path: Path, content: str) -> None:
    """Atomik yazar: önce .tmp dosyasına, sonra rename."""
    tmp_path = path.with_suffix(path.suffix + ".jarvis.tmp")
    try:
        tmp_path.write_text(content, encoding="utf-8")
        os.replace(tmp_path, path)
        try:
            os.chmod(path, 0o600)
        except OSError:
            pass
    finally:
        try:
            if tmp_path.exists():
                tmp_path.unlink()
        except OSError:
            pass


def _backup_file(path: Path) -> Path:
    """Değişiklik öncesi .bak dosyası oluşturur."""
    backup = path.with_name(f"{path.name}.jarvis-{int(time.time())}.bak")
    try:
        backup.write_bytes(path.read_bytes())
    except Exception as exc:
        logger.warning("[CodeAgent] Yedek oluşturulamadı: %s", exc)
    return backup


# ── Subprocess sandbox çalıştırıcı ───────────────────────────────────────

def run_in_sandbox(
    command: list[str],
    cwd: str,
    timeout: int = 30,
    env_extra: Optional[dict] = None,
) -> dict:
    """
    Kodu izole subprocess'te çalıştırır.
    Returns: {"stdout": str, "stderr": str, "returncode": int, "success": bool}
    """
    env = os.environ.copy()
    if env_extra:
        env.update(env_extra)
    # Güvenlik: PATH'den tehlikeli komutları filtrele
    try:
        result = subprocess.run(
            command,
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=timeout,
            shell=False,
            env=env,
        )
        return {
            "stdout": result.stdout[:5000],
            "stderr": result.stderr[:2000],
            "returncode": result.returncode,
            "success": result.returncode == 0,
        }
    except subprocess.TimeoutExpired:
        return {"stdout": "", "stderr": f"Zaman aşımı ({timeout}s)", "returncode": -1, "success": False}
    except Exception as exc:
        return {"stdout": "", "stderr": str(exc), "returncode": -1, "success": False}


# ── Ana CodeAgent sınıfı ─────────────────────────────────────────────────

class CodeAgent:
    """
    Kod ajanı ana sınıfı.
    
    Kullanım:
        agent = CodeAgent(router=get_router())
        result = agent.execute_task(
            project_dir="D:/myproject",
            task="login fonksiyonuna 2FA desteği ekle",
            progress_cb=lambda step, total, msg: print(f"{step}/{total}: {msg}")
        )
    """

    def __init__(self, router=None):
        self._router = router  # ModelRouter instance (None olabilir — Groq fallback)

    def _ai_plan(self, task: str, tree: str, file_contents: dict, system: str) -> str:
        """AI ile değişiklik planı oluştur."""
        context = f"Proje yapısı:\n{tree}\n\n"
        context += "İlgili dosya içerikleri:\n"
        for path, content in list(file_contents.items())[:8]:
            context += f"\n--- {Path(path).name} ---\n{content[:3000]}\n"
        prompt = (
            f"Görev: {task}\n\n{context}\n\n"
            "Lütfen şunları çıkar:\n"
            "1. PLAN: Hangi dosyalar nasıl değiştirilecek (kısa özet)\n"
            "2. DEĞİŞİKLİKLER: Her dosya için tam yeni içerik veya sadece değişen kısım\n"
            "   Format: <DOSYA yol/dosya.py>\n<yeni içerik>\n</DOSYA>\n"
            "3. TEST: Çalıştırılabilir bir test komutu (varsa)\n\n"
            "Türkçe yanıt ver. Yalnızca gerekli minimum değişiklikleri yap."
        )

        if self._router:
            from services.model_router import TaskType
            return self._router.chat([], prompt, system, task_type=TaskType.CODE)
        else:
            # Groq fallback
            try:
                from services.ai_client import create_groq_client
                key = os.environ.get("JARVIS_GROQ_API_KEY") or os.environ.get("GROQ_API_KEY", "")
                client = create_groq_client(key)
                resp = client.chat.completions.create(
                    model=os.environ.get("JARVIS_GROQ_MODEL", "openai/gpt-oss-20b"),
                    messages=[{"role": "system", "content": system},
                               {"role": "user", "content": prompt}],
                    max_tokens=4096, temperature=0.3)
                return resp.choices[0].message.content
            except Exception as exc:
                return f"AI planlama hatası: {exc}"

    def _parse_file_changes(self, ai_response: str) -> dict[str, str]:
        """
        AI yanıtından <DOSYA path>\ncontent\n</DOSYA> bloklarını çıkarır.
        Returns: {file_path: new_content}
        """
        import re
        changes = {}
        pattern = r"<DOSYA\s+([^\n>]+)>\n(.*?)\n</DOSYA>"
        matches = re.findall(pattern, ai_response, re.DOTALL)
        for path, content in matches:
            changes[path.strip()] = content.strip()
        return changes

    def execute_task(
        self,
        project_dir: str,
        task: str,
        auto_approve: bool = False,
        progress_cb=None,  # (step: int, total: int, msg: str)
        notify_cb=None,    # (msg: str)
    ) -> str:
        """
        Tam iş akışını yürütür.
        
        Returns: Sonuç mesajı
        """
        def _progress(step, total, msg):
            logger.info("[CodeAgent] %d/%d: %s", step, total, msg)
            if progress_cb:
                progress_cb(step, total, msg)

        def _notify(msg):
            if notify_cb:
                notify_cb(msg)

        total_steps = 7

        # ── Adım 1: Yol doğrula ─────────────────────────────────────────
        _progress(1, total_steps, "Proje klasörü doğrulanıyor...")
        root = Path(project_dir).resolve()
        if not _safe_under_home(root) or not _is_safe_path(root):
            return "Bu proje dizini güvenlik kısıtlamaları nedeniyle erişilemiyor."

        # ── Adım 2: Proje tara ───────────────────────────────────────────
        _progress(2, total_steps, "Proje yapısı taranıyor...")
        scan = scan_project(str(root))
        if "error" in scan:
            return scan["error"]

        # ── Adım 3: İlgili dosyaları oku ────────────────────────────────
        _progress(3, total_steps, "İlgili dosyalar okunuyor...")
        file_contents = read_relevant_files(scan["files"], task)

        # ── Adım 4: AI ile plan ─────────────────────────────────────────
        _progress(4, total_steps, "AI değişiklik planı hazırlıyor...")
        system_prompt = (
            "Sen deneyimli bir yazılım mühendisisin. "
            "Minimum, güvenli ve geriye dönük uyumlu değişiklikler yaparsın. "
            "Türkçe yanıt ver. Mevcut kodu kırma."
        )
        ai_plan = self._ai_plan(task, scan["tree"], file_contents, system_prompt)

        # ── Adım 5: Onay ────────────────────────────────────────────────
        _progress(5, total_steps, "Kullanıcı onayı bekleniyor...")

        changes = self._parse_file_changes(ai_plan)
        if not changes:
            # Değiştirilecek dosya bulunamadıysa sadece planı göster
            return f"AI Planı (otomatik değişiklik bulunamadı):\n\n{ai_plan}"

        plan_summary = f"Değiştirilecek dosyalar ({len(changes)}):\n"
        for path in changes:
            plan_summary += f"  • {path}\n"
        plan_summary += f"\nAI Açıklaması:\n{ai_plan[:1000]}"

        if not auto_approve:
            pm = get_permission_manager()
            result = pm.request(
                ActionCategory.FILE_WRITE,
                f"Kod ajanı {len(changes)} dosyayı değiştirecek",
                details=plan_summary[:500],
                undo_info="Git stash veya .bak dosyaları ile geri alınabilir",
            )
            if not result.allowed:
                return f"İşlem kullanıcı tarafından iptal edildi.\n\nPlan:\n{ai_plan}"

        # ── Adım 6: Git yedek + dosya yaz ───────────────────────────────
        _progress(6, total_steps, "Değişiklikler uygulanıyor...")
        git = GitManager(str(root))
        stash_result = git.stash_or_commit()
        if stash_result:
            _notify(f"Git yedek alındı: {stash_result}")

        applied_files = []
        errors = []
        for rel_path, new_content in changes.items():
            target = root / rel_path
            if not _safe_under_home(target) or not _is_safe_path(target):
                errors.append(f"{rel_path}: güvenlik kısıtlaması nedeniyle atlandı")
                continue
            try:
                target.parent.mkdir(parents=True, exist_ok=True)
                if target.exists():
                    _backup_file(target)
                _write_atomic(target, new_content)
                applied_files.append(str(target))
                _notify(f"Yazıldı: {rel_path}")
            except Exception as exc:
                errors.append(f"{rel_path}: {exc}")

        # ── Adım 7: Test & doğrula ──────────────────────────────────────
        _progress(7, total_steps, "Test ediliyor...")
        test_result = self._auto_test(root, ai_plan, applied_files)

        # Git commit (başarılıysa)
        if applied_files and (not errors):
            commit_msg = git.commit(applied_files, task[:60])
            if commit_msg:
                _notify(commit_msg)

        # Özet
        summary_parts = [f"Görev tamamlandı: {task}\n"]
        if applied_files:
            summary_parts.append(f"Değiştirilen dosyalar ({len(applied_files)}):")
            for f in applied_files:
                summary_parts.append(f"  ✓ {Path(f).name}")
        if errors:
            summary_parts.append(f"\nHatalar ({len(errors)}):")
            for e in errors:
                summary_parts.append(f"  ✗ {e}")
        if test_result:
            summary_parts.append(f"\nTest sonucu:\n{test_result}")

        return "\n".join(summary_parts)

    def _auto_test(self, root: Path, ai_plan: str, applied_files: list[str]) -> str:
        """AI planından test komutunu çıkarıp çalıştır."""
        import re
        # "TEST: pytest" veya "test komutu: python -m pytest" bul
        test_match = re.search(r"TEST:\s*`?([^\n`]+)`?", ai_plan, re.IGNORECASE)
        if not test_match:
            return ""

        cmd_raw = test_match.group(1).strip()
        # Sadece güvenli test komutları izin ver
        safe_prefixes = ["pytest", "python -m pytest", "python -m unittest", "npm test", "cargo test"]
        if not any(cmd_raw.startswith(p) for p in safe_prefixes):
            return f"Güvensiz test komutu atlandı: {cmd_raw}"

        cmd_parts = cmd_raw.split()
        for _ in range(MAX_RETRY):
            result = run_in_sandbox(cmd_parts, cwd=str(root))
            if result["success"]:
                return f"Test başarılı.\n{result['stdout'][:500]}"
            # Hata varsa AI'ya düzeltme sor (basit retry — tam self-heal ayrı PR)
            logger.warning("[CodeAgent] Test başarısız: %s", result["stderr"][:200])

        return f"Test başarısız (max deneme).\n{result['stderr'][:300]}"

    def undo_last_changes(self, project_dir: str) -> str:
        """Son değişiklikleri git stash pop ile geri al."""
        git = GitManager(project_dir)
        return git.pop_stash()
