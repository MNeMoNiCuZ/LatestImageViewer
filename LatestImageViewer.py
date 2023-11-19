import subprocess
import sys

def install(package):
    subprocess.check_call([sys.executable, "-m", "pip", "install", package])

# Check and install Pillow (PIL)
try:
    from PIL import Image, ImageTk
except ImportError:
    install('pillow')

# Check and install screeninfo
try:
    from screeninfo import get_monitors
except ImportError:
    install('screeninfo')

# Check and install tkinter (messagebox is part of tkinter)
try:
    import tkinter as tk
    import tkinter.messagebox as messagebox
except ImportError:
    print("Tkinter is not installed. Please install it as it's a fundamental part of this application.")

# Check and install send2trash
try:
    import send2trash
except ImportError:
    install('send2trash')

# Standard library modules (no need to install these)
import os
import time
import configparser


#Print the monitor setup
#for monitor in get_monitors():
#    print(monitor)

class LatestImageViewer:
    # Initialize the main application window and its variables
    def __init__(self, root):
        self.root = root

        # Initialize folder_path_var before loading settings
        self.folder_path_var = tk.StringVar()
        self.config = configparser.ConfigParser()
        self.settings_file = 'settings.ini'
        self.load_settings()

        # Additional initializations
        self.current_image_path = None
        self.right_click_start_time = None
        self.hold_threshold = 500  # Time in milliseconds
        self.right_mouse_held = False
        self.prev_mouse_y = None
        self.zoom_level = 1  # Starting zoom level
        self.manual_navigation_active = False  # Flag for manual navigation
        self.is_current_image_latest = False
        self.setup_widgets()  # Set up the UI components

        # Set focus to the root window to ensure it receives key events
        self.root.focus_set()

        self.last_zoom_update_time = time.time()
        self.zoom_active = False
        self.loaded_image = None  # To store the loaded PIL image
        self.user_has_zoomed = False  # Flag to track zoom state

        self.root.bind("<Configure>", self.on_window_resize)
        self.root.bind("<Alt-Return>", self.toggle_fullscreen)

        # Set focus based on whether the path is preloaded
        if self.save_path_var.get() and self.folder_path:
            self.start_button.focus_set()
        else:
            self.path_entry.focus_set()

    # Load application settings from the INI file
    def load_settings(self):
        """Load settings from the INI file."""
        self.config.read(self.settings_file)
        self.zoom_speed = self.config.getfloat('Defaults', 'zoom_speed', fallback=0.1)
        self.update_interval = self.config.getint('Defaults', 'update_interval', fallback=1)
        self.zoom_update_delay = self.config.getfloat('Defaults', 'zoom_update_delay', fallback=0.001)
        self.folder_path = self.config.get('Defaults', 'folder_path', fallback='')
        if self.folder_path:
            self.folder_path_var.set(self.folder_path)

    # Save current settings to the INI file
    def save_settings(self):
        """Save current settings to the INI file."""
        self.config['Defaults'] = {
            'zoom_speed': str(self.zoom_speed),
            'update_interval': str(self.update_interval),
            'zoom_update_delay': str(self.zoom_update_delay),
            'save_path': str(self.save_path_var.get())
        }
        if self.save_path_var.get():
            self.config['Defaults']['folder_path'] = self.folder_path_var.get()
        else:
            self.config['Defaults']['folder_path'] = ''
        with open(self.settings_file, 'w') as configfile:
            self.config.write(configfile)

    # Toggle fullscreen mode on and off
    def toggle_fullscreen(self, event=None):
        self.fullscreen_active = not getattr(self, 'fullscreen_active', False)
        if self.fullscreen_active:
            # Calculate the center point of the window
            window_x = self.root.winfo_x() + self.root.winfo_width() // 2
            window_y = self.root.winfo_y() + self.root.winfo_height() // 2

            # Find the monitor that contains the window's center point
            for monitor in get_monitors():
                if (monitor.x <= window_x < monitor.x + monitor.width and
                    monitor.y <= window_y < monitor.y + monitor.height):
                    # Move and resize window to cover the entire monitor
                    self.root.geometry(f'{monitor.width}x{monitor.height}+{monitor.x}+{monitor.y}')
                    self.root.attributes('-fullscreen', True)
                    break
            self.root.bind("<Escape>", self.toggle_fullscreen)
        else:
            self.root.attributes('-fullscreen', False)
            self.root.geometry('800x600')  # Reset to default size when exiting fullscreen
            self.root.unbind("<Escape>")

    # Setup the UI components and bind event handlers
    def setup_widgets(self):
        # Instruction label
        self.instruction_label = tk.Label(self.root, text="Enter the path to the image folder")
        self.instruction_label.pack()

        # Entry for folder path
        self.path_entry = tk.Entry(self.root, textvariable=self.folder_path_var, width=100)
        self.path_entry.pack()

        # Checkbox for saving the folder path
        self.save_path_var = tk.BooleanVar(value=self.config.getboolean('Defaults', 'save_path', fallback=False))
        self.save_path_checkbox = tk.Checkbutton(self.root, text="Save path", variable=self.save_path_var)
        self.save_path_checkbox.pack()

        # Button to start viewing
        self.start_button = tk.Button(self.root, text="Let's Go!", command=self.start_viewing)
        self.start_button.pack()

        # Label to display images
        self.label = tk.Label(self.root)
        self.label.pack(fill=tk.BOTH, expand=True)

        # Set focus to the root window to ensure it receives key events
        self.root.focus_set()

    # Navigate to the previous image
    def show_previous_image(self, event=None):
        print("Left arrow key pressed")
        self.change_image(-1)
        self.reset_zoom()

    # Navigate to the next image
    def show_next_image(self, event=None):
        print("Right arrow key pressed")
        self.change_image(1)
        self.reset_zoom()

    # Jump to the first image when the Home key is pressed
    def on_home_press(self, event=None):
        print("Home key pressed")
        self.jump_to_image(0)

    # Jump to the last image when the End key is pressed
    def on_end_press(self, event=None):
        print("End key pressed")
        self.jump_to_image(-1)

    # Jump backwards 10 images when Page Up is pressed
    def on_pgup_press(self, event=None):
        print("Page Up key pressed")
        self.change_image(-10)

    # Jump forward 10 images when Page Down is pressed
    def on_pgdn_press(self, event=None):
        print("Page Down key pressed")
        self.change_image(10)

    # Navigate through images quickly using the mouse scroll wheel
    def scroll_through_images(self, event):
        step = -1 if event.delta > 0 else 1  # Adjust based on scroll direction
        self.change_image(step)
        self.reset_zoom()

    # Change the current image by a given step
    def change_image(self, step):
        image_files = self.get_image_files()
        if not image_files:
            return

        if self.current_image_path is None:
            self.current_image_path = self.find_latest_image()

        try:
            current_index = image_files.index(os.path.basename(self.current_image_path))
        except ValueError:
            current_index = 0 if step > 0 else len(image_files) - 1

        new_index = max(0, min(current_index + step, len(image_files) - 1))

        if new_index != current_index:
            self.current_image_path = os.path.join(self.folder_path, image_files[new_index])
            self.update_image_display()
            self.reset_zoom()

        # Update the is_current_image_latest flag
        self.is_current_image_latest = self.current_image_path == os.path.join(self.folder_path, image_files[-1])

        self.reset_zoom()


    # Jump to a specific image based on its index
    def jump_to_image(self, index):
        image_files = self.get_image_files()
        if not image_files:
            return

        # Jump to the first or last image based on the index
        if index == -1:
            index = len(image_files) - 1  # Jump to the last image
        elif index == 0:
            index = 0  # Jump to the first image

        self.current_image_path = os.path.join(self.folder_path, image_files[index])
        self.update_image_display()
        self.manual_navigation_active = True
        self.reset_zoom()

    # Reset the zoom level to its default state
    def reset_zoom(self):
        self.zoom_level = 1
        self.user_has_zoomed = False
        self.update_image_display()

    # Update the display with the current image
    def update_image_display(self):
        if self.current_image_path:
            self.loaded_image = Image.open(self.current_image_path)
            if not self.user_has_zoomed:
                self.scale_and_display_image()
            else:
                self.update_zoomed_image()

    # Retrieve a list of image files from the current folder
    def get_image_files(self):
        image_files = [f for f in os.listdir(self.folder_path) if f.lower().endswith(('.png', '.jpg', '.jpeg', '.gif'))]
        return sorted(image_files, key=lambda x: os.path.getmtime(os.path.join(self.folder_path, x)))

    # Handle mouse movement for zoom functionality
    def on_mouse_move(self, event):
        if not self.right_mouse_held or not self.current_image_path:
            return

        if self.prev_mouse_y is not None:
            # Determine zoom direction based on mouse Y movement
            zoom_speed = self.zoom_speed  # Adjust for faster or slower zoom
            if event.y_root < self.prev_mouse_y:  # Mouse moved up, zoom in
                self.zoom_level = min(self.zoom_level + zoom_speed, 10)  # Max zoom 10000%
            elif event.y_root > self.prev_mouse_y:  # Mouse moved down, zoom out
                self.zoom_level = max(self.zoom_level - zoom_speed, 0.1)  # Min zoom 1%

            self.update_zoomed_image()
        self.user_has_zoomed = True  # Set flag when user zooms

        self.prev_mouse_y = event.y_root
        current_time = time.time()
        if current_time - self.last_zoom_update_time > self.zoom_update_delay:
            self.update_zoomed_image()
            self.last_zoom_update_time = current_time

    # Update the displayed image based on the current zoom level
    def update_zoomed_image(self):
        if self.loaded_image and self.user_has_zoomed:
            try:
                # Calculate the new size based on the zoom level
                new_width = int(self.loaded_image.width * self.zoom_level)
                new_height = int(self.loaded_image.height * self.zoom_level)

                # Use faster resampling for interactive zooming
                resampling = Image.Resampling.NEAREST if self.zoom_active else Image.Resampling.LANCZOS

                # Resize the image using the appropriate resampling method
                resized_image = self.loaded_image.resize((new_width, new_height), resampling)

                # Convert to a format that Tkinter label can use
                image_tk = ImageTk.PhotoImage(resized_image)

                # Update the label with the new image
                self.label.config(image=image_tk)
                self.label.image = image_tk
            except Exception as e:
                print(f"Error updating zoomed image: {e}")

    # Show the right-click context menu
    def show_context_menu(self, event):
        # Check if the right mouse was not held for long (indicating a quick right-click)
        if not self.right_mouse_held:
            try:
                self.context_menu.tk_popup(event.x_root, event.y_root)
            finally:
                self.context_menu.grab_release()

    # Handle the right mouse button press event
    def on_right_click_press(self, event):
        self.right_mouse_held = True
        self.zoom_active = True
        self.label.bind("<Motion>", self.on_mouse_move)  # Bind mouse movement

    # Handle the right mouse button release event
    def on_right_click_release(self, event):
        self.right_mouse_held = False
        self.zoom_active = False
        self.label.unbind("<Motion>")  # Unbind mouse movement
        self.show_context_menu(event)

    # Delete menu item
    def delete_image(self, event=None):
        # Check if there's a current image to delete
        if not self.current_image_path:
            print("No image to delete.")
            return

        # Ask for confirmation before deleting the image
        response = messagebox.askyesno("Delete Image", "Are you sure you want to delete this image?")
        if response:
            try:
                image_files = self.get_image_files()
                current_index = image_files.index(os.path.basename(self.current_image_path))

                send2trash.send2trash(self.current_image_path)
                print(f"Moved {self.current_image_path} to recycle bin")

                # Update the image list and adjust the index
                image_files = self.get_image_files()  # Refresh the image list
                if current_index >= len(image_files):
                    current_index = len(image_files) - 1  # Move to the previous image if the last one was deleted

                if image_files:  # Check if there are still images left
                    self.current_image_path = os.path.join(self.folder_path, image_files[current_index])
                    self.update_image_display()
                else:
                    self.current_image_path = None
                    self.label.config(image='')  # Clear the display if no images are left
                    print("No more images in the folder.")

            except Exception as e:
                print(f"Error moving image to recycle bin: {e}")

    # Jump to latest image
    def go_to_latest_image(self):
        self.jump_to_image(-1)  # -1 indicates the last image in the list

    # Start the image viewing process and hide initial setup components
    def start_viewing(self):

        # Right-click context menu
        self.context_menu = tk.Menu(self.root, tearoff=0)
        self.context_menu.add_command(label="Fullscreen [ALT + ENTER]", command=self.toggle_fullscreen)
        self.context_menu.add_command(label="Delete Image [DEL]", command=self.delete_image)
        self.context_menu.add_command(label="Go to Latest Image [END]", command=self.go_to_latest_image)

        # Binding right-click to the context menu
        self.label.bind("<Button-3>", self.show_context_menu)

        # Bind right-click press and release
        self.label.bind("<ButtonPress-3>", self.on_right_click_press)
        self.label.bind("<ButtonRelease-3>", self.on_right_click_release)
    
        # Bind input  keys and scroll wheel for image navigation
        self.root.bind("<Left>", self.show_previous_image)
        self.root.bind("<Right>", self.show_next_image)
        self.root.bind("<MouseWheel>", self.scroll_through_images)
        self.root.bind("<Home>", self.on_home_press)
        self.root.bind("<End>", self.on_end_press)
        self.root.bind("<Prior>", self.on_pgup_press)  # Page Up
        self.root.bind("<Next>", self.on_pgdn_press)   # Page Down
        self.root.bind("<Delete>", self.delete_image)

        # Retrieve and save the folder path
        self.folder_path = self.folder_path_var.get()
        self.save_settings()  # Save settings including folder path if 'Save path' is checked

        # Initialize with the latest image
        self.current_image_path = self.find_latest_image()
        if self.current_image_path:
            self.loaded_image = Image.open(self.current_image_path)
            self.scale_and_display_image()

        # Schedule the first call to update_image
        self.root.after(self.update_interval * 1000, self.update_image)

        # Hide the folder selection interface
        self.instruction_label.pack_forget()
        self.path_entry.pack_forget()
        self.start_button.pack_forget()
        self.save_path_checkbox.pack_forget()  # Hide the 'Save path' checkbox

        # Optional: Bind window resize event (if necessary)
        self.root.bind("<Configure>", self.on_window_resize)

        self.is_current_image_latest = True  # Initially set to True

    # Handle window resize events
    def on_window_resize(self, event=None):
        if not self.user_has_zoomed and not self.zoom_active:
            if self.current_image_path:
                self.scale_and_display_image()

    # Scale the image to fit within the application window
    def scale_image_to_fit(self, image):
        window_width, window_height = self.root.winfo_width(), self.root.winfo_height()
        image_width, image_height = image.size

        # Calculate the scaling factor to maintain aspect ratio
        scale_factor = min(window_width / image_width, window_height / image_height)
        new_size = (int(image_width * scale_factor), int(image_height * scale_factor))

        return image.resize(new_size, Image.Resampling.LANCZOS)

    def update_image(self):
        print("update_image called")  # Debugging
        latest_image_path = self.find_latest_image()
        image_files = self.get_image_files()

        if not image_files:
            self.root.after(self.update_interval * 1000, self.update_image)
            return

        # Check if the current image is the latest in the folder
        current_image_is_latest = self.current_image_path == os.path.join(self.folder_path, image_files[-1])

        print(f"Current image is latest: {current_image_is_latest}")  # Debugging
        print(f"is_current_image_latest flag: {self.is_current_image_latest}")  # Debugging

        # Update if the current image is the latest and a new latest image is found
        if latest_image_path != self.current_image_path:
            if self.is_current_image_latest:
                self.current_image_path = latest_image_path
                self.loaded_image = Image.open(self.current_image_path)
                self.scale_and_display_image()
                self.is_current_image_latest = True  # Ensure the flag remains true after updating
            else:
                # Here you can decide what to do if the current image is not the latest
                pass

        self.root.after(self.update_interval * 1000, self.update_image)


    # Scale the image to fit the window while maintaining aspect ratio
    def scale_and_display_image(self):
        try:
            window_width, window_height = self.root.winfo_width(), self.root.winfo_height()
            image_width, image_height = self.loaded_image.size

            scale_factor = min(window_width / image_width, window_height / image_height)
            new_size = (int(image_width * scale_factor), int(image_height * scale_factor))

            resized_image = self.loaded_image.resize(new_size, Image.Resampling.LANCZOS)
            image_tk = ImageTk.PhotoImage(resized_image)

            self.label.config(image=image_tk)
            self.label.image = image_tk
        except Exception as e:
            print(f"Error scaling image: {e}")

    # Find the most recently added or modified image in the folder
    def find_latest_image(self):
        image_files = self.get_image_files()
        if not image_files:
            return None

        latest_file = max(image_files, key=lambda x: os.path.getmtime(os.path.join(self.folder_path, x)))
        return os.path.join(self.folder_path, latest_file)

if __name__ == "__main__":
    root = tk.Tk()
    root.title("Latest Image Viewer")
    root.geometry("800x600")  # Set the initial size of the window (width x height)

    app = LatestImageViewer(root)
    root.mainloop()