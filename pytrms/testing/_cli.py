"""@file _cli.py

"""
import time
import logging

log = logging.getLogger()  # get our root logger, before anyone else does!

import click

from .ionimock import IoniMock
try:
    from . import msg_info
    from .._base.mqttclient import MqttClientBase
    from ..clients.mqtt import _build_header, _build_data_element
except ImportError:
    # using the cli?!
    from pytrms.testing import msg_info
    from pytrms._base.mqttclient import MqttClientBase
    from pytrms.clients.mqtt import _build_header, _build_data_element

# ===================== BEGIN CLI ======================= #

@click.group()
@click.option("--mqtt-host", type=str, default="localhost", help="an alternative host for Mosquitto broker (overrides env-var 'PD_MQTT_HOST')")
@click.option("--mqtt-port", type=int, default=1883, help="an alternative port for Mosquitto broker (overrides env-var 'PD_MQTT_PORT')")
@click.option('-v', "--verbose", count=True, help="increase logging output (can be given up to four times)")
@click.pass_context
def cli(ctx, mqtt_host, mqtt_port, verbose):

    # ========== begin setup logging =========== #
    # our root logger defines the appropriate level at which
    # to log any messages (nothing lower will ever pass this):
    log.setLevel({
            0: logging.ERROR,
            1: logging.WARN,
            2: logging.INFO,
            3: logging.DEBUG,
            4: logging.NOTSET,
        }[min(max(0, verbose), 4)])
    # attach a console-stream-handler to our root logger...
    sh = logging.StreamHandler()
    sh.setFormatter(logging.Formatter(
        "[%(levelname)s]\t%(message)s",
        datefmt="%Y:%m:%dT%H:%M:%S.000"))
    log.addHandler(sh)

    ctx.obj = IoniMock(mqtt_host, mqtt_port)

@cli.command()
@click.pass_context
def run(ctx):
    mock = ctx.obj

    click.echo("Mocked out IoniTOF in 'ACQ_Idle' mode...")
    click.echo()
    click.echo("...hit CTRL-C to shut down the Mock!")
    try:
        while True: time.sleep(600)
    except KeyboardInterrupt:
        click.echo(" received CTRL-C, cleanup...")
    finally:
        log.info("shutting down...")
        mock.disconnect()

@cli.command()
@click.option('-f', "--record-file", required=True, help="Path to the recorded file (e.g. *.REPLAY)")
@click.option("--speed", default=1.0, type=float, help="Accelerate replay by this factor (may be < 1 for slower speed)")
@click.option('-n', "--dry-run", is_flag=True, help="Don't do anything, just show what would happen")
@click.pass_context
def replay(ctx, record_file, speed, dry_run):
    # a) one-off: lade replay file, play, fertig
    # b) daemon: warte auf IC_command und hoffe, dass es ein .REPLAY file gibt ?!
    #     |__ muss man etwas konstruieren, wsl. muss man die start_0.py hacken...
    #     ...oder oben im IC_Command einen hook einbauen, der ein >REPLAY neben dem .h5 file findet ?!
    mock = ctx.obj

    mock.connect()
    mock.play(record_file, speed, dry_run)
    mock.disconnect()

@cli.command()
@click.option('-f', "--record-file", required=True, help="Path to the recorded file (e.g. *.REPLAY)")
@click.option("--speed", default=1.0, type=float, help="Accelerate replay by this factor (may be < 1 for slower speed)")
@click.option('-n', "--dry-run", is_flag=True, help="Don't do anything, just show what would happen")
@click.pass_context
def daemon(ctx, record_file, speed, dry_run):
    # a) one-off: lade replay file, play, fertig
    # b) daemon: warte auf IC_command und hoffe, dass es ein .REPLAY file gibt ?!
    #     |__ muss man etwas konstruieren, wsl. muss man die start_0.py hacken...
    #     ...oder oben im IC_Command einen hook einbauen, der ein >REPLAY neben dem .h5 file findet ?!
    mock = ctx.obj
    mock.connect()

    print("Mocked out IoniTOF in 'ACQ_Idle' mode...")
    print()
    print("...hit CTRL-C to shut down the Mock!")
    try:
        while True:
            while not mock.is_running:
                time.sleep(60e-3)

            mock.play(record_file, speed, dry_run)  # blocks
            continue

    except KeyboardInterrupt:
        print(" received CTRL-C, cleanup...")
    finally:
        log.info("shutting down...")
        mock.disconnect()


# ======================= END CLI ======================= #

if __name__ == '__main__':
    cli(obj=None)

