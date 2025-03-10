from io import BytesIO
from flask import send_file, abort, Response, request
from utils.general import get_blob

def setup_data_routes(app):
    # Data routes
    @app.route('/assets/images/<img_name>')
    def serve_image(img_name):
        try:
            blob = get_blob('images', img_name)

            # Use send_file to send the image file directly
            img_bytes = blob.download_as_bytes()
            img_file = BytesIO(img_bytes)
            img_file.seek(0)
            return send_file(img_file, mimetype=blob.content_type)
        except Exception as e:
            abort(500, e)

    @app.route('/assets/music/<filename>')
    def get_music(filename):
        blob = get_blob('music', filename)

        # Load blob to get the size
        blob.reload()

        file_size = blob.size
        print(f"File size: {file_size}")

        # Partial content handling
        range_header = request.headers.get('Range', None)
        if not range_header:
            return Response(
                blob.download_as_bytes(),
                200,
                mimetype='audio/mpeg',
                headers={'Content-Length': str(file_size)}
            )

        byte_range = range_header.strip().split('=')[1]
        byte_range = byte_range.split('-')
        start = int(byte_range[0])
        end = int(byte_range[1]) if byte_range[1] else file_size - 1

        if start >= file_size or end >= file_size:
            abort(416)

        chunk = blob.download_as_bytes(start=start, end=end + 1)
        response = Response(
            chunk,
            206,
            mimetype='audio/mpeg',
            headers={
                'Content-Range': f'bytes {start}-{end}/{file_size}',
                'Accept-Ranges': 'bytes',
                'Content-Length': str(end - start + 1),
            }
        )
        return response
