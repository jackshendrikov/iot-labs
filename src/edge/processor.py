from src.models.aggregated_data import AggregatedData
from src.models.processed_agent_data import ProcessedAgentData, RoadState

Z_BASELINE = 16500

WARNING_Y_THRESHOLD = 13500
BAD_Y_THRESHOLD = 15000
WARNING_Z_DEVIATION_THRESHOLD = 33200
BAD_Z_DEVIATION_THRESHOLD = 34200


def process_agent_data(agent_data: AggregatedData) -> ProcessedAgentData:
    """Класифікує стан дорожнього покриття за даними акселерометра.

    Пороги підібрані під наявний навчальний датасет так, щоб:
    - більша частина траси відображалась як `GOOD`;
    - `WARNING` утворював короткі проблемні відрізки;
    - `BAD` залишався рідкісними локальними інцидентами.
    """
    accelerometer = agent_data.accelerometer
    y_spike = abs(accelerometer.y)
    z_deviation = abs(accelerometer.z - Z_BASELINE)

    if y_spike >= BAD_Y_THRESHOLD or z_deviation >= BAD_Z_DEVIATION_THRESHOLD:
        road_state = RoadState.BAD
    elif y_spike >= WARNING_Y_THRESHOLD or z_deviation >= WARNING_Z_DEVIATION_THRESHOLD:
        road_state = RoadState.WARNING
    else:
        road_state = RoadState.GOOD

    return ProcessedAgentData(road_state=road_state, agent_data=agent_data)
