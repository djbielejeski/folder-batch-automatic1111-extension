import copy
import os

import gradio as gr
from PIL import Image

import modules.scripts as scripts
from modules.processing import process_images
from modules.shared import opts, cmd_opts, state, sd_model


class FolderBatchImage:
    def __init__(self, image: Image = None):
        self.image = image
        self.transformed_image: Image = None
        self.width, self.height = self.image.size


class Script(scripts.Script):

    def __init__(self):
        self.images: list[FolderBatchImage] = []
        self.img2img_component = gr.Image()
        self.img2img_gallery = gr.Gallery()
        self.img2img_w_slider = gr.Slider()
        self.img2img_h_slider = gr.Slider()

        # might be able to save cnet settings like this
        # x = copy(scripts.scripts_img2img)
        # print(x)

        # external_code_test.py
        # external_code.update_cn_script_in_place(self.scripts, self.script_args, self.cn_units)

    def title(self):
        return "Folder-Batch"

    def show(self, is_img2img):
        return is_img2img

    def get_images_from_directory(self, directory_path: str) -> list[FolderBatchImage]:
        images: list[FolderBatchImage] = []
        print(f"directory_path: {directory_path}")
        if directory_path is None or not os.path.exists(directory_path):
            raise Exception(f"Directory not found: '{directory_path}'.")
        else:
            image_extensions = ['.jpg', '.jpeg', '.png']
            image_names = [
                file_name for file_name in os.listdir(directory_path)
                if any(file_name.endswith(ext) for ext in image_extensions)
            ]

            if len(image_names) <= 0:
                raise Exception(f"No images (*.png, *.jpg, *.jpeg) found in '{directory_path}'.")

            # Open the images and convert them to np.ndarray
            for i, image_name in enumerate(image_names):
                image_path = os.path.join(directory_path, image_name)

                # Convert the image
                image = Image.open(image_path)

                if not image.mode == "RGB":
                    image = image.convert("RGB")

                images.append(FolderBatchImage(image=image))

        return images

    # How the script's is displayed in the UI. See https://gradio.app/docs/#components
    # for the different UI components you can use and how to create them.
    # Most UI components can return a value, such as a boolean for a checkbox.
    # The returned values are passed to the run method as parameters.
    def ui(self, is_img2img):

        gr.HTML("<h1 style='border-bottom: 1px solid #eee; margin: 12px 0px 8px !important'>Folder Batch</h1>")
        gr.HTML("<div><a style='color: #0969da;' href='https://github.com/djbielejeski/folder-batch-automatic1111-extension' target='_blank'>Folder Batch Github</a></div>")

        # Directory Path Row
        directory_path_gr = gr.Textbox(
            label="Directory",
            value="",
            elem_id="fb_video_directory",
            interactive=True,
            visible=True,
            info="Path to directory containing the images to process."
        )
        gr.HTML("<div style='margin: 16px 0px !important; border-bottom: 1px solid #eee;'></div>")

        # Video Source Info Row
        folder_info_gr = gr.HTML("")

        # Click handlers and UI Updaters

        # If the user inputs a directory, update the img2img sections
        def src_change(directory_path: str):
            self.images = self.get_images_from_directory(directory_path)
            if len(self.images) > 0:
                # Update the img2img settings via the existing Gradio controls
                first_image = self.images[0]
                message = f"<div style='color: #333'>{len(self.images)} images found.</div>"

                return {
                    self.img2img_component: gr.update(value=first_image.image),
                    self.img2img_w_slider: gr.update(value=first_image.width),
                    self.img2img_h_slider: gr.update(value=first_image.height),
                    folder_info_gr: gr.update(value=message)
                }
            else:
                self.images = []
                error_message = "" if directory_path is None or directory_path == "" else "Invalid directory, unable to find images in directory."
                return {
                    self.img2img_component: gr.update(value=None),
                    self.img2img_w_slider: gr.update(value=512),
                    self.img2img_h_slider: gr.update(value=512),
                    folder_info_gr: gr.update(value=f"<div style='color: red'>{error_message}</div>")
                }

        # Watch the path for change
        directory_path_gr.change(
            fn=src_change,
            inputs=[directory_path_gr],
            outputs=[
                self.img2img_component,
                self.img2img_w_slider,
                self.img2img_h_slider,
                folder_info_gr,
            ]
        )

        return ()

    # From: https://github.com/LonicaMewinsky/gif2gif/blob/main/scripts/gif2gif.py
    # Grab the img2img image components for update later
    # Maybe there's a better way to do this?
    def after_component(self, component, **kwargs):
        if component.elem_id == "img2img_image":
            self.img2img_component = component
            return self.img2img_component
        if component.elem_id == "img2img_gallery":
            self.img2img_gallery = component
            return self.img2img_gallery
        if component.elem_id == "img2img_width":
            self.img2img_w_slider = component
            return self.img2img_w_slider
        if component.elem_id == "img2img_height":
            self.img2img_h_slider = component
            return self.img2img_h_slider

    """
    This function is called if the script has been selected in the script dropdown.
    It must do all processing and return the Processed object with results, same as
    one returned by processing.process_images.

    Usually the processing is done by calling the processing.process_images function.

    args contains all values returned by components from ui()
    """

    def run(
            self,
            p,
    ):

        if len(self.images) > 0:
            print(f"# of images to process: {len(self.images)}")

            state.job_count = len(self.images) * p.n_iter
            state.job_no = 0

            # Loop over all the images and process them
            for i, image in enumerate(self.images):
                if state.skipped: state.skipped = False
                if state.interrupted: break

                # Progress indicator
                state.job = f"{state.job_no + 1} out of {state.job_count}"

                cp = copy.copy(p)

                # Set the Img2Img reference image to the image and set the dimensions
                cp.init_images = [image.image]
                cp.width = image.width
                cp.height = image.height

                # Process the image via the normal Img2Img pipeline
                proc = process_images(cp)

                # Capture the output, we will use this to re-create our video
                image.transformed_image = proc.images[0]

                cp.close()

            # Show the user what we generated
            proc.images = [image.transformed_image for image in self.images]

        else:
            proc = process_images(p)

        return proc
