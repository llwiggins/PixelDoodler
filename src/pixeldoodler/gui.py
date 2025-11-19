import tkinter as tk
from tkinter import filedialog, messagebox
from tkinter import ttk
from PIL import Image, ImageTk, ImageDraw, ImageColor
import numpy as np
import os
try:
    from tkinterdnd2 import DND_FILES, TkinterDnD
    HAS_DND = True
except ImportError:
    HAS_DND = False

# Predefined colours with numbers assigned, change this if more classes are required
PREDEFINED_COLOURS = [
    (1, "Red",    "#ff0000"),
    (2, "Blue",   "#0000ff"),
    (3, "Green",  "#00ff00"),
    (4, "Yellow", "#ffff00"),
    (5, "Purple", "#800080"),
]

COLOUR_TO_NUMBER = {hex_color: number for number, name, hex_color in PREDEFINED_COLOURS}
NUMBER_TO_COLOUR = {number: hex_color for number, name, hex_color in PREDEFINED_COLOURS}


class Doodler:
    def __init__(self):
        if HAS_DND:
            self.root = TkinterDnD.Tk()
        else:
            self.root = tk.Tk()

        self.root.title("PixelDoodler")
        self.root.geometry("800x800")

        # Style/theme
        style = ttk.Style(self.root)
        try:
            style.theme_use("clam")
        except tk.TclError:
            # fallback if "clam" not available
            pass

        default_font = ("Segoe UI", 10)
        self.root.option_add("*Font", default_font)

        style.configure("TButton", padding=5)
        style.configure("TLabelframe.Label", font=("Segoe UI", 10, "bold"))

        self.image = None
        self.mask = None
        self.draw = None
        self.stroke_stack = []
        self.erased_strokes = []
        self.brush_color = PREDEFINED_COLOURS[0][2]
        self.brush_size = 5.0
        self.brush_number = PREDEFINED_COLOURS[0][0]
        self.last_x, self.last_y = None, None
        self.has_strokes = False
        self.zoom_level = 1.0
        self.min_zoom = 0.5
        self.max_zoom = 3.0
        self.image_files = []
        self.current_index = -1
        self.current_folder = ""
        self.is_eraser = False
        self.brush_preview_id = None
        self.preview_x, self.preview_y = None, None

        # empty-state message on canvas
        self.empty_message_id = None

        self._build_layout()
        self._bind_events()

        # Initialise drag & drop if supported
        if HAS_DND:
            self._init_dnd()
            self.status_label.config(
                text="Drag & drop a folder of images or .npy files, or click 'Open Folder' to begin."
            )
        else:
            self.status_label.config(
                text="Open a folder of images or .npy files to begin. (Install 'tkinterdnd2' for drag & drop.)"
            )

        self.show_empty_message()

    # UI
    def _build_layout(self):
        self.root.configure(bg="#f2f2f3")

        
        top = ttk.Frame(self.root, padding=(8, 6))
        top.pack(side=tk.TOP, fill=tk.X)

        nav_frame = ttk.Frame(top)
        nav_frame.pack(side=tk.LEFT)

        self.open_button = ttk.Button(nav_frame, text="Open Folder", command=self.open_folder_dialog)
        self.open_button.pack(side=tk.LEFT, padx=(0, 6))

        self.prev_button = ttk.Button(nav_frame, text="◀ Previous", command=self.previous_image, state=tk.DISABLED)
        self.prev_button.pack(side=tk.LEFT, padx=2)

        self.next_button = ttk.Button(nav_frame, text="Next ▶", command=self.next_image, state=tk.DISABLED)
        self.next_button.pack(side=tk.LEFT, padx=2)

        brush_frame = ttk.LabelFrame(top, text="Brush")
        brush_frame.pack(side=tk.LEFT, padx=15)

        ttk.Label(brush_frame, text="Class:").pack(side=tk.LEFT, padx=(4, 2))
        self.selected_color = tk.StringVar(self.root, PREDEFINED_COLOURS[0][1])
        self.color_combo = ttk.Combobox(
            brush_frame,
            textvariable=self.selected_color,
            values=[name for _, name, _ in PREDEFINED_COLOURS],
            state="readonly",
            width=10,
        )
        self.color_combo.bind("<<ComboboxSelected>>", self._on_color_combo)
        self.color_combo.pack(side=tk.LEFT, padx=(0, 6))

        # colour swatch
        self.color_display = tk.Label(
            brush_frame,
            text="  ",
            bg=self.brush_color,
            relief="solid",
            width=2,
        )
        self.color_display.pack(side=tk.LEFT, padx=(0, 6))

        # Brush size
        ttk.Label(brush_frame, text="Size:").pack(side=tk.LEFT)
        self.brush_size_var = tk.IntVar(value=int(self.brush_size))

        self.brush_size_label = ttk.Label(brush_frame, text=f"{self.brush_size:.1f}px")
        self.brush_size_label.pack(side=tk.LEFT, padx=(0, 4))

        self.brush_size_slider = ttk.Scale(
            brush_frame,
            from_=0.5,
            to=50,
            orient=tk.HORIZONTAL,
        )
        self.brush_size_slider.set(self.brush_size)
        self.brush_size_slider.configure(command=self.update_brush_size_from_slider)
        self.brush_size_slider.pack(side=tk.LEFT, padx=(2, 4), ipadx=30)

        self.eraser_var = tk.BooleanVar(value=False)
        self.erase_button = ttk.Checkbutton(
            brush_frame,
            text="Eraser",
            variable=self.eraser_var,
            command=self.toggle_eraser
        )
        self.erase_button.pack(side=tk.LEFT, padx=(10, 4))

        right_frame = ttk.Frame(top)
        right_frame.pack(side=tk.RIGHT)

        zoom_frame = ttk.LabelFrame(right_frame, text="Zoom")
        zoom_frame.pack(side=tk.LEFT, padx=(0, 10))

        self.zoom_label = ttk.Label(zoom_frame, text=f"{self.zoom_level:.1f}×")
        self.zoom_label.pack(side=tk.LEFT, padx=(4, 2))

        self.zoom_slider = ttk.Scale(
            zoom_frame,
            from_=self.min_zoom,
            to=self.max_zoom,
            orient=tk.HORIZONTAL,
        )
        self.zoom_slider.set(self.zoom_level)
        self.zoom_slider.configure(command=self.update_zoom)
        self.zoom_slider.pack(side=tk.LEFT, padx=4, ipadx=40)

        actions_frame = ttk.Frame(right_frame)
        actions_frame.pack(side=tk.LEFT)

        self.clear_button = ttk.Button(actions_frame, text="Clear Mask", command=self.clear_mask)
        self.clear_button.pack(side=tk.LEFT, padx=4)

        self.save_button = ttk.Button(actions_frame, text="Save Mask", command=self.save_brush_strokes)
        self.save_button.pack(side=tk.LEFT, padx=4)

        center = ttk.Frame(self.root)
        center.pack(fill=tk.BOTH, expand=True, padx=6, pady=(0, 6))

        self.canvas = tk.Canvas(center, bg="#1e1e1e", highlightthickness=0)
        self.canvas.grid(row=0, column=0, sticky="nsew")

        vbar = ttk.Scrollbar(center, orient=tk.VERTICAL, command=self.canvas.yview)
        vbar.grid(row=0, column=1, sticky="ns")

        hbar = ttk.Scrollbar(center, orient=tk.HORIZONTAL, command=self.canvas.xview)
        hbar.grid(row=1, column=0, sticky="ew")

        self.canvas.configure(xscrollcommand=hbar.set, yscrollcommand=vbar.set)

        center.rowconfigure(0, weight=1)
        center.columnconfigure(0, weight=1)

        self.canvas.bind("<Configure>", self._on_canvas_configure)

        status = ttk.Frame(self.root, padding=(6, 3))
        status.pack(side=tk.BOTTOM, fill=tk.X)

        self.status_label = ttk.Label(status, text="", anchor="w")
        self.status_label.pack(side=tk.LEFT, fill=tk.X, expand=True)

        self.pos_label = ttk.Label(status, text="", width=20, anchor="e")
        self.pos_label.pack(side=tk.RIGHT)

    def _bind_events(self):
        self.canvas.bind("<B1-Motion>", self.paint)
        self.canvas.bind("<Motion>", self.update_brush_preview)
        self.root.bind("<ButtonRelease-1>", self.reset_last_coords)
        self.root.bind("<space>", self.next_image)

    def show_empty_message(self):
        """Show center message on the canvas when no image is loaded."""
        self.canvas.delete("all")
        self.brush_preview_id = None

        w = self.canvas.winfo_width() or 600
        h = self.canvas.winfo_height() or 400
        msg = (
            "Drag & drop a folder of images or .npy files here\n"
            "or click 'Open Folder' to start labelling."
        )

        self.empty_message_id = self.canvas.create_text(
            w // 2,
            h // 2,
            text=msg,
            fill="#cccccc",
            font=("Segoe UI", 14),
            justify="center"
        )

    def _on_canvas_configure(self, event):
        """Keep the empty message centered if it exists."""
        if self.empty_message_id is not None:
            self.canvas.coords(self.empty_message_id, event.width // 2, event.height // 2)

    def _init_dnd(self):
        """
        Initialise drag & drop for folders using tkinterdnd2.
        The user can drop a folder anywhere on the main window.
        """
        self.root.drop_target_register(DND_FILES)
        self.root.dnd_bind("<<Drop>>", self.on_drop)

    def on_drop(self, event):
        """
        Handle dropped items. We only accept folders.
        event.data can contain one or more paths.
        """
        if not event.data:
            return

        paths = self.root.tk.splitlist(event.data)
        folder_path = None

        for p in paths:
            if os.path.isdir(p):
                folder_path = p
                break

        if not folder_path:
            messagebox.showerror("Drag & Drop", "Please drag and drop a folder (not a file).")
            return

        self.load_folder(folder_path)

    def open_folder_dialog(self):
        """Show a dialog, then call load_folder()."""
        folder_path = filedialog.askdirectory()
        if not folder_path:
            return
        self.load_folder(folder_path)

    def load_folder(self, folder_path):
        """
        Load a folder path directly (used by dialog and drag & drop).
        Accepts both image files and .npy files.
        """
        self.image_files = [
            f for f in os.listdir(folder_path)
            if f.lower().endswith((".png", ".jpg", ".jpeg", ".gif", ".tif", ".tiff", ".npy"))
        ]
        self.image_files.sort()

        if not self.image_files:
            messagebox.showerror("Error", "No image or .npy files found in the selected folder.")
            return

        self.current_folder = folder_path
        self.current_index = 0
        self.load_image(self.image_files[self.current_index])
        self.update_navigation_buttons()
        self.status_label.config(
            text=f"Loaded {len(self.image_files)} files from {folder_path}"
        )

    def _npy_to_image(self, array):
        """
        Convert a numpy array to a Pillow RGBA image for display.
        Handles:
        - 2D arrays -> grayscale
        - 3D arrays with channels last (H, W, C)
        """
        arr = np.array(array)

        # If it's boolean, map to 0/255
        if arr.dtype == bool:
            arr = arr.astype(np.uint8) * 255

        if arr.ndim == 2:
            # normalize to 0-255 if not already
            arr = arr.astype(np.float32)
            min_val, max_val = arr.min(), arr.max()
            if max_val > min_val:
                arr = (arr - min_val) / (max_val - min_val) * 255.0
            arr = arr.astype(np.uint8)
            img = Image.fromarray(arr, mode="L").convert("RGBA")
            return img

        if arr.ndim == 3:
            if arr.shape[0] in (1, 3, 4) and arr.shape[2] not in (1, 3, 4):
                arr = np.transpose(arr, (1, 2, 0))

            if arr.shape[2] == 1:
                arr = arr[:, :, 0]
                return self._npy_to_image(arr)

            if arr.shape[2] in (3, 4):
                if arr.dtype != np.uint8:
                    arr = arr.astype(np.float32)
                    min_val, max_val = arr.min(), arr.max()
                    if max_val > min_val:
                        arr = (arr - min_val) / (max_val - min_val) * 255.0
                    arr = arr.astype(np.uint8)

                mode = "RGB" if arr.shape[2] == 3 else "RGBA"
                img = Image.fromarray(arr, mode=mode)
                if mode == "RGB":
                    img = img.convert("RGBA")
                return img

        arr = arr.astype(np.float32)
        arr = (arr - arr.min()) / (arr.max() - arr.min() + 1e-8) * 255.0
        arr = arr.astype(np.uint8)
        if arr.ndim >= 2:
            arr = arr[..., 0]
        img = Image.fromarray(arr, mode="L").convert("RGBA")
        return img

    def load_image(self, image_file):
        image_path = os.path.join(self.current_folder, image_file)
        try:
            if image_file.lower().endswith(".npy"):
                arr = np.load(image_path)
                self.image = self._npy_to_image(arr)
            else:
                self.image = Image.open(image_path).convert("RGBA")
        except FileNotFoundError:
            messagebox.showerror("Error", f"File not found: {image_path}")
            return
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load file:\n{image_path}\n\n{e}")
            return

        self.mask = Image.new("RGBA", self.image.size, (0, 0, 0, 0))
        self.draw = ImageDraw.Draw(self.mask)
        self.stroke_stack.clear()
        self.erased_strokes.clear()
        self.has_strokes = False

        self.display_image()
        self.status_label.config(text=f"{image_file} ({self.current_index+1}/{len(self.image_files)})")

    def display_image(self):
        if self.image is None:
            self.show_empty_message()
            return

        zoom_w = int(self.image.width * self.zoom_level)
        zoom_h = int(self.image.height * self.zoom_level)

        zoomed_image = self.image.resize((zoom_w, zoom_h), Image.Resampling.LANCZOS)
        zoomed_mask = self.mask.resize((zoom_w, zoom_h), Image.Resampling.NEAREST)

        combined_image = Image.alpha_composite(zoomed_image, zoomed_mask)
        photo = ImageTk.PhotoImage(combined_image)

        self.canvas.delete("all")
        self.empty_message_id = None  # remove empty-state message
        self.brush_preview_id = None
        self.canvas.create_image(0, 0, anchor=tk.NW, image=photo)
        self.canvas.image = photo

        self.canvas.config(scrollregion=(0, 0, zoom_w, zoom_h))

        if self.preview_x is not None and self.preview_y is not None:
            class E:
                pass
            e = E()
            e.x, e.y = self.preview_x, self.preview_y
            self.update_brush_preview(e)

    def update_navigation_buttons(self):
        self.prev_button.config(
            state=tk.NORMAL if self.current_index > 0 else tk.DISABLED
        )
        self.next_button.config(
            state=tk.NORMAL if self.current_index < len(self.image_files) - 1 else tk.DISABLED
        )

    def next_image(self, event=None):
        if self.has_strokes:
            if not self.save_brush_strokes():
                return

        if self.current_index < len(self.image_files) - 1:
            self.current_index += 1
            self.load_image(self.image_files[self.current_index])
            self.update_navigation_buttons()

    def previous_image(self, event=None):
        if self.current_index > 0:
            self.current_index -= 1
            self.load_image(self.image_files[self.current_index])
            self.update_navigation_buttons()

    # ------------------------------------------------------------------ Drawing
    def paint(self, event):
        if self.image is None or self.mask is None:
            return

        x, y = event.x, event.y
        self.preview_x, self.preview_y = x, y

        self.pos_label.config(text=f"x={x} y={y}")

        if self.last_x is not None and self.last_y is not None:
            scaled_x1 = int(self.last_x / self.zoom_level)
            scaled_y1 = int(self.last_y / self.zoom_level)
            scaled_x2 = int(x / self.zoom_level)
            scaled_y2 = int(y / self.zoom_level)

            line_width = max(1, int(round(self.brush_size)))
            radius = max(1, int(round(self.brush_size / 2.0)))

            if self.is_eraser:
                self.draw.line(
                    [scaled_x1, scaled_y1, scaled_x2, scaled_y2],
                    fill=(0, 0, 0, 0),
                    width=line_width,
                )
                self.draw.ellipse(
                    [
                        scaled_x2 - radius,
                        scaled_y2 - radius,
                        scaled_x2 + radius,
                        scaled_y2 + radius,
                    ],
                    fill=(0, 0, 0, 0),
                    outline=(0, 0, 0, 0),
                )
            else:
                self.draw.line(
                    [scaled_x1, scaled_y1, scaled_x2, scaled_y2],
                    fill=self.brush_color,
                    width=line_width,
                )
                self.draw.ellipse(
                    [
                        scaled_x2 - radius,
                        scaled_y2 - radius,
                        scaled_x2 + radius,
                        scaled_y2 + radius,
                    ],
                    fill=self.brush_color,
                    outline=self.brush_color,
                )

            self.stroke_stack.append(
                (self.brush_color, scaled_x1, scaled_y1, scaled_x2, scaled_y2, self.brush_size)
            )
            self.has_strokes = True

        self.last_x, self.last_y = x, y
        self.display_image()

    def reset_last_coords(self, event):
        self.last_x, self.last_y = None, None

    def _on_color_combo(self, event=None):
        name = self.selected_color.get()
        for number, cname, hex_color in PREDEFINED_COLOURS:
            if cname == name:
                self.brush_number = number
                self.brush_color = hex_color
                break
        self.color_display.config(bg=self.brush_color)
        self.is_eraser = False
        self.eraser_var.set(False)

    def update_brush_size_from_slider(self, val):
        self.brush_size = float(val)
        self.brush_size_label.config(text=f"{self.brush_size:.1f}px")
        if self.preview_x is not None and self.preview_y is not None:
            class E: pass
            e = E(); e.x, e.y = self.preview_x, self.preview_y
            self.update_brush_preview(e)

    def toggle_eraser(self):
        self.is_eraser = self.eraser_var.get()
        if self.preview_x is not None and self.preview_y is not None:
            class E: pass
            e = E(); e.x, e.y = self.preview_x, self.preview_y
            self.update_brush_preview(e)

    def update_zoom(self, val):
        self.zoom_level = float(val)
        self.zoom_label.config(text=f"{self.zoom_level:.1f}×")
        self.display_image()

    def update_brush_preview(self, event):
        if self.image is None:
            return

        self.preview_x, self.preview_y = event.x, event.y
        self.pos_label.config(text=f"x={event.x} y={event.y}")

        base_radius = max(1, int(round(self.brush_size / 2.0)))
        r = max(1, int(round(base_radius * self.zoom_level)))

        x1, y1 = event.x - r, event.y - r
        x2, y2 = event.x + r, event.y + r

        outline = "#ffffff" if not self.is_eraser else "#00ffff"

        if self.brush_preview_id is None:
            self.brush_preview_id = self.canvas.create_oval(
                x1, y1, x2, y2, outline=outline, width=1
            )
        else:
            self.canvas.coords(self.brush_preview_id, x1, y1, x2, y2)
            self.canvas.itemconfig(self.brush_preview_id, outline=outline)

    def clear_mask(self):
        if self.image is None:
            return
        self.mask = Image.new("RGBA", self.image.size, (0, 0, 0, 0))
        self.draw = ImageDraw.Draw(self.mask)
        self.stroke_stack.clear()
        self.erased_strokes.clear()
        self.has_strokes = False
        self.display_image()
        self.status_label.config(text="Mask cleared.")

    def save_brush_strokes(self):
        if self.mask is None:
            messagebox.showerror("Error", "No brush strokes to save.")
            return False

        if self.image_files:
            current_image_file = self.image_files[self.current_index]
            base_name, ext = os.path.splitext(current_image_file)
            default_save_path_npy = os.path.join(self.current_folder, f"{base_name}_mask.npy")
            default_save_path_png = os.path.join(self.current_folder, f"{base_name}_mask.png")
        else:
            default_save_path_npy = filedialog.asksaveasfilename(
                defaultextension=".npy",
                filetypes=[("NumPy files", "*.npy")],
            )
            default_save_path_png = filedialog.asksaveasfilename(
                defaultextension=".png",
                filetypes=[("PNG files", "*.png")],
            )

        if not default_save_path_npy or not default_save_path_png:
            return False

        mask_array = np.array(self.mask)
        num_array = np.zeros((mask_array.shape[0], mask_array.shape[1]), dtype=np.uint8)

        for number, _, hex_color in PREDEFINED_COLOURS:
            r, g, b = ImageColor.getrgb(hex_color)
            color_mask = (mask_array[..., :3] == [r, g, b]).all(axis=-1)
            num_array[color_mask] = number

        background_mask = (mask_array[..., 3] == 0)
        num_array[background_mask] = 0

        try:
            np.save(default_save_path_npy, num_array)

            black_background = Image.new("RGB", self.mask.size, (0, 0, 0))
            rgb_mask = Image.alpha_composite(
                black_background.convert("RGBA"), self.mask
            ).convert("RGB")
            rgb_mask.save(default_save_path_png)

            msg = f"Saved:\n{default_save_path_npy}\n{default_save_path_png}"
            messagebox.showinfo("Saved", msg)
            self.status_label.config(text="Mask saved.")
            return True
        except Exception as e:
            messagebox.showerror("Error", f"Failed to save the file:\n{e}")
            return False


if __name__ == "__main__":
    app = Doodler()
    app.root.mainloop()