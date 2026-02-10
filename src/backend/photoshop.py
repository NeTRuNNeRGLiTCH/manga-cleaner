import os
import cv2
import tempfile
import numpy as np

#////////////////////////#
#  COM INTEROP BRIDGE    #
#////////////////////////#

class PhotoshopBridge:
    @staticmethod
    def send_to_ps(original_rgb: np.ndarray, cleaned_rgb: np.ndarray) -> str:
        try:
            import win32com.client
        except ImportError:
            return "Library 'pywin32' missing"

        try:
            ps = win32com.client.Dispatch("Photoshop.Application")
            
            temp_path = tempfile.gettempdir()
            orig_file = os.path.join(temp_path, "mc_orig.png")
            clean_file = os.path.join(temp_path, "mc_clean.png")
            
            cv2.imwrite(orig_file, cv2.cvtColor(original_rgb, cv2.COLOR_RGB2BGR))
            cv2.imwrite(clean_file, cv2.cvtColor(cleaned_rgb, cv2.COLOR_RGB2BGR))

            ps.Open(orig_file)
            doc = ps.ActiveDocument
            doc.ActiveLayer.Name = "Original Page"

            ps.Open(clean_file)
            ps.ActiveDocument.Selection.SelectAll()
            ps.ActiveDocument.Selection.Copy()
            ps.ActiveDocument.Close(2)

            doc.Paste()
            doc.ActiveLayer.Name = "Titan Cleaner Result"
            
            os.remove(orig_file)
            os.remove(clean_file)
            
            return "Success"
        except Exception as e:
            return f"COM Error: {str(e)}"