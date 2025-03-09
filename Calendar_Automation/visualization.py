import logging
from datetime import datetime

logger = logging.getLogger(__name__)


def generate_html_visualization(results, filename):
    """Generate a human-readable HTML visualization of scheduling results"""
    filled_appointments = results.get('filled_appointments', [])
    unfilled_appointments = results.get('unfilled_appointments', [])

    html_content = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Scheduling Results</title>
        <style>
            body { font-family: Arial, sans-serif; margin: 20px; }
            h1 { color: #333; }
            table { border-collapse: collapse; width: 100%; margin-bottom: 20px; }
            th, td { padding: 8px; text-align: left; border: 1px solid #ddd; }
            th { background-color: #f2f2f2; }
            .unfilled { background-color: #ffeeee; }
            .validation-failed { color: red; }
        </style>
    </head>
    <body>
        <h1>Scheduling Results</h1>

        <h2>Filled Appointments (${filled_count})</h2>
        <table>
            <tr>
                <th>Client ID</th>
                <th>Type</th>
                <th>Date</th>
                <th>Start Time</th>
                <th>End Time</th>
            </tr>
    """.replace("${filled_count}", str(len(filled_appointments)))

    # Add filled appointments
    for app in filled_appointments:
        client_id = app.get('id', '')
        app_type = app.get('type', '')
        start_time = app.get('start_time', '')
        end_time = app.get('end_time', '')

        # Parse and format datetimes
        start_dt = datetime.fromisoformat(start_time)
        end_dt = datetime.fromisoformat(end_time)
        date = start_dt.strftime('%Y-%m-%d')
        start_time_str = start_dt.strftime('%H:%M')
        end_time_str = end_dt.strftime('%H:%M')

        html_content += f"""
            <tr>
                <td>{client_id}</td>
                <td>{app_type}</td>
                <td>{date}</td>
                <td>{start_time_str}</td>
                <td>{end_time_str}</td>
            </tr>
        """

    html_content += """
        </table>

        <h2>Unfilled Appointments (${unfilled_count})</h2>
        <table>
            <tr>
                <th>Client ID</th>
                <th>Type</th>
            </tr>
    """.replace("${unfilled_count}", str(len(unfilled_appointments)))

    # Add unfilled appointments
    for app in unfilled_appointments:
        client_id = app.get('id', '')
        app_type = app.get('type', '')

        html_content += f"""
            <tr class="unfilled">
                <td>{client_id}</td>
                <td>{app_type}</td>
            </tr>
        """

    html_content += """
        </table>

        <h2>Validation Results</h2>
    """

    # Add validation results
    validation = results.get('validation', {})
    is_valid = validation.get('valid', False)
    issues = validation.get('issues', [])

    if is_valid:
        html_content += "<p>✓ Schedule is valid. No issues detected.</p>"
    else:
        html_content += "<p class='validation-failed'>✗ Schedule validation failed:</p><ul>"
        for issue in issues:
            html_content += f"<li class='validation-failed'>{issue}</li>"
        html_content += "</ul>"

    html_content += """
    </body>
    </html>
    """

    try:
        with open(filename, 'w', encoding='utf-8') as f:
            f.write(html_content)
        logger.info(f"Successfully generated HTML visualization at {filename}")
        return True
    except Exception as e:
        logger.error(f"Error generating HTML visualization: {str(e)}")
        return False
