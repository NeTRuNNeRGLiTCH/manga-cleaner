#/////////////////////////////////#
#    4-STACK HISTORY MANAGER      #
#/////////////////////////////////#

class HistoryManager:
    def __init__(self, limit=20):
        self.limit = limit
        self.img_undo = []
        self.img_redo = []
        self.mask_undo = []
        self.mask_redo = []

    def push_image_action(self, x, y, patch):
        self.img_undo.append((x, y, patch.copy()))
        self.img_redo.clear()
        if len(self.img_undo) > self.limit:
            self.img_undo.pop(0)

    def pop_image_undo(self, current_img):
        if not self.img_undo: return None
        x, y, patch = self.img_undo.pop()
        h, w = patch.shape[:2]
        redo_patch = current_img[y:y+h, x:x+w].copy()
        self.img_redo.append((x, y, redo_patch))
        return (x, y, patch)

    def pop_image_redo(self, current_img):
        if not self.img_redo: return None
        x, y, patch = self.img_redo.pop()
        h, w = patch.shape[:2]
        undo_patch = current_img[y:y+h, x:x+w].copy()
        self.img_undo.append((x, y, undo_patch))
        return (x, y, patch)

    def push_mask_state(self, mask_qimage):
        self.mask_undo.append(mask_qimage.copy())
        self.mask_redo.clear()
        if len(self.mask_undo) > self.limit:
            self.mask_undo.pop(0)

    def pop_mask_undo(self, current_mask):
        if not self.mask_undo: return None
        self.mask_redo.append(current_mask.copy())
        return self.mask_undo.pop()

    def pop_mask_redo(self, current_mask):
        if not self.mask_redo: return None
        self.mask_undo.append(current_mask.copy())
        return self.mask_redo.pop()
