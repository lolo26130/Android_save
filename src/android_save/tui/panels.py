"""
Panneaux d'arborescence pour la vue de synchronisation.

Ce module fournit :class:`FileTreePanel`, un widget Textual affichant
l'arborescence des fichiers avec un code couleur par statut.

.. list-table:: Code couleur
   :header-rows: 1

   * - Couleur
     - Statut
   * - Vert
     - À copier (:attr:`~android_save.sync.FileStatus.TO_COPY`)
   * - Jaune
     - À mettre à jour (:attr:`~android_save.sync.FileStatus.TO_UPDATE`)
   * - Gris (dim)
     - Identique (:attr:`~android_save.sync.FileStatus.IDENTICAL`)
   * - Rouge (italique)
     - Orphelin (:attr:`~android_save.sync.FileStatus.ORPHAN`)

.. seealso::
    :class:`android_save.tui.app.AndroidSaveApp` qui instancie ces panneaux.
"""

from __future__ import annotations

from typing import Literal

from rich.text import Text
from textual.message import Message
from textual.widgets import Tree
from textual.widgets.tree import TreeNode

from android_save.sync import FileStatus, SyncEntry, SyncPlan, format_size

Side = Literal["remote", "local"]

STATUS_STYLE: dict[FileStatus, str] = {
    FileStatus.TO_COPY: "#2ecc71",
    FileStatus.TO_UPDATE: "#f1c40f",
    FileStatus.IDENTICAL: "dim",
    FileStatus.ORPHAN: "italic #e74c3c",
}

_STATUS_ICON: dict[FileStatus, str] = {
    FileStatus.TO_COPY: "+",
    FileStatus.TO_UPDATE: "~",
    FileStatus.IDENTICAL: " ",
    FileStatus.ORPHAN: "?",
}


class FileTreePanel(Tree):
    """Panneau d'arborescence coloré selon l'état de synchronisation.

    Hérite de :class:`textual.widgets.Tree`. Peut représenter le côté
    téléphone ou le côté backup selon ``side``.

    Émet :class:`FileTreePanel.Scrolled` à chaque changement de position
    verticale, permettant à :class:`~android_save.tui.app.AndroidSaveApp`
    de synchroniser les deux panneaux.

    :param title: Titre affiché en en-tête du panneau.

    Usage typique (dans :meth:`~android_save.tui.app.AndroidSaveApp._refresh_panels`)::

        panel = FileTreePanel(title="Téléphone")
        panel.load_plan(plan, side="remote")
    """

    class Scrolled(Message):
        """Émis quand la position de défilement verticale change.

        :param panel: Le panneau source de l'événement.
        :param y: Nouvelle position verticale en pixels.
        """

        def __init__(self, panel: "FileTreePanel", y: float) -> None:
            super().__init__()
            self.panel = panel
            self.y = y

    def __init__(self, title: str, **kwargs) -> None:
        super().__init__(title, **kwargs)
        self.guide_depth = 3
        self.show_root = True
        self._path_to_line: dict[str, int] = {}

    def watch_scroll_y(self, y: float) -> None:
        """Publie :class:`Scrolled` à chaque défilement vertical."""
        self.post_message(self.Scrolled(self, y))

    def scroll_to_path(self, rel_path: str) -> None:
        """Fait défiler le panneau pour centrer verticalement le fichier indiqué.

        :param rel_path: Chemin relatif du fichier (clé de :attr:`_path_to_line`).
        """
        if rel_path not in self._path_to_line:
            return
        line = self._path_to_line[rel_path]
        visible = self.scrollable_content_region.height
        self.scroll_to(y=max(0, line - visible // 2), animate=False)

    def load_plan(self, plan: SyncPlan, side: Side) -> None:
        """Charge et affiche le plan de synchronisation.

        Construit l'arborescence en regroupant les entrées par répertoire.
        Les dossiers sont automatiquement créés. La position de chaque fichier
        (en lignes depuis la racine) est mémorisée dans :attr:`_path_to_line`
        pour le suivi automatique lors des transferts.

        :param plan: Plan calculé par :class:`~android_save.sync.SyncEngine`.
        :param side: ``"remote"`` pour le téléphone, ``"local"`` pour le backup.
        """
        self.clear()
        self._path_to_line = {}
        root_label = plan.remote_root if side == "remote" else plan.local_root
        self.root.set_label(root_label)

        tree: dict[str, TreeNode] = {}
        line = [1]  # ligne 0 = racine

        def get_node(dir_path: str) -> TreeNode:
            if dir_path in tree:
                return tree[dir_path]
            parts = dir_path.split("/")
            parent_path = "/".join(parts[:-1])
            parent = get_node(parent_path) if parent_path else self.root
            node = parent.add(parts[-1], expand=True)
            tree[dir_path] = node
            line[0] += 1  # le nœud répertoire prend une ligne
            return node

        for entry in sorted(plan.entries.values(), key=lambda e: e.relative_path):
            if "/" in entry.relative_path:
                dir_part, file_part = entry.relative_path.rsplit("/", 1)
            else:
                dir_part, file_part = "", entry.relative_path

            if side == "local" and entry.status == FileStatus.TO_COPY:
                continue
            if side == "remote" and entry.status == FileStatus.ORPHAN:
                continue

            label = self._make_label(entry, file_part, side)
            parent = get_node(dir_part) if dir_part else self.root
            parent.add_leaf(label)
            self._path_to_line[entry.relative_path] = line[0]
            line[0] += 1

    def _make_label(self, entry: SyncEntry, filename: str, side: Side) -> Text:
        """Construit le libellé coloré d'un fichier.

        :param entry: Entrée de synchronisation.
        :param filename: Nom de fichier seul (sans répertoire).
        :param side: Côté affiché.
        :return: Objet :class:`rich.text.Text` prêt à l'affichage.
        """
        style = STATUS_STYLE[entry.status]
        icon = _STATUS_ICON[entry.status]

        size = entry.remote_size if side == "remote" else entry.local_size
        size_str = f"  {format_size(size)}" if size is not None else ""

        text = Text()
        text.append(f"{icon} ", style=style)
        text.append(filename, style=style)
        text.append(size_str, style="dim")
        return text
