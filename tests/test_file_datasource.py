from src.file_datasource import FileDatasource


def test_batch_and_cycle_reading(tmp_path):
    """Перевіряє, що FileDatasource читає пакетами та циклічно."""
    acc_tmp = tmp_path / "acc.csv"
    gps_tmp = tmp_path / "gps.csv"

    acc_tmp.write_text("x,y,z\n0.1,0.2,0.3\n0.4,0.5,0.6\n0.7,0.8,0.9\n1.0,1.1,1.2", encoding="utf-8")
    gps_tmp.write_text("longitude,latitude\n1.0,2.0\n3.0,4.0\n5.0,6.0\n7.0,8.0\n", encoding="utf-8")

    datasource = FileDatasource(str(acc_tmp), str(gps_tmp), batch_size=2)
    datasource.start_reading()

    # Перше читання: перші два рядки
    batch1 = datasource.read()
    assert len(batch1) == 2
    assert batch1[0].accelerometer.x == 0.1
    assert batch1[1].accelerometer.x == 0.4

    # Друге читання: наступні два рядки
    batch2 = datasource.read()
    assert len(batch2) == 2
    assert batch2[0].accelerometer.x == 0.7
    assert batch2[1].accelerometer.x == 1.0

    # Третє читання: повертається на початок (перезавантаження)
    batch3 = datasource.read()
    assert len(batch3) == 2
    assert batch3[0].accelerometer.x == 0.1
    assert batch3[1].accelerometer.x == 0.4

    datasource.stop_reading()
