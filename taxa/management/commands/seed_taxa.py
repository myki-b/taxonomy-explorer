"""Populate the database with a broad, curated set of species.

Each name is pushed through the same fetch-and-cache service the rest of the
app uses, so seeding exercises exactly the production code path.
"""
import time

from django.core.management.base import BaseCommand

from taxa.models import Taxon
from taxa.services import GBIFError, fetch_and_cache_taxon

# A deliberately wide spread: several kingdoms, and a cluster of domestic and
# veterinary species, so the browsable tree has real breadth.
SPECIES = [
    # --- Domestic and veterinary species -----------------------------------
    "Canis familiaris", "Felis catus", "Equus caballus", "Equus asinus",
    "Bos taurus", "Ovis aries", "Capra hircus", "Sus scrofa",
    "Gallus gallus", "Anas platyrhynchos", "Meleagris gallopavo",
    "Oryctolagus cuniculus", "Cavia porcellus", "Mesocricetus auratus",
    "Mustela putorius", "Rattus norvegicus", "Mus musculus",
    "Melopsittacus undulatus", "Serinus canaria", "Camelus dromedarius",
    "Lama glama", "Vicugna pacos", "Danio rerio", "Apis mellifera",

    # --- Wild mammals -------------------------------------------------------
    "Vulpes vulpes", "Canis lupus", "Lycaon pictus", "Panthera leo",
    "Panthera tigris", "Panthera pardus", "Panthera onca", "Acinonyx jubatus",
    "Puma concolor", "Lynx lynx", "Felis silvestris", "Crocuta crocuta",
    "Suricata suricatta", "Meles meles", "Lutra lutra", "Enhydra lutris",
    "Martes martes", "Mustela erminea", "Ursus arctos", "Ursus maritimus",
    "Ailuropoda melanoleuca", "Loxodonta africana", "Elephas maximus",
    "Giraffa camelopardalis", "Hippopotamus amphibius", "Ceratotherium simum",
    "Diceros bicornis", "Equus quagga", "Cervus elaphus", "Capreolus capreolus",
    "Alces alces", "Rangifer tarandus", "Bison bison", "Gorilla gorilla",
    "Pan troglodytes", "Pongo pygmaeus", "Macaca mulatta", "Lemur catta",
    "Balaenoptera musculus", "Physeter macrocephalus", "Orcinus orca",
    "Tursiops truncatus", "Phoca vitulina", "Odobenus rosmarus",
    "Erinaceus europaeus", "Sciurus vulgaris", "Castor fiber", "Talpa europaea",
    "Phascolarctos cinereus", "Vombatus ursinus", "Ornithorhynchus anatinus",
    "Tachyglossus aculeatus", "Myrmecophaga tridactyla", "Dasypus novemcinctus",
    "Pteropus vampyrus",

    # --- Birds --------------------------------------------------------------
    "Haliaeetus leucocephalus", "Aquila chrysaetos", "Falco peregrinus",
    "Bubo bubo", "Tyto alba", "Strix aluco", "Vultur gryphus",
    "Corvus corax", "Pica pica", "Erithacus rubecula", "Turdus merula",
    "Passer domesticus", "Cyanistes caeruleus", "Parus major",
    "Hirundo rustica", "Apus apus", "Alcedo atthis", "Dendrocopos major",
    "Cuculus canorus", "Columba livia", "Sturnus vulgaris", "Ardea cinerea",
    "Cygnus olor", "Anser anser", "Phoenicopterus roseus",
    "Pelecanus onocrotalus", "Aptenodytes forsteri", "Spheniscus demersus",
    "Struthio camelus", "Dromaius novaehollandiae", "Ara macao",
    "Psittacus erithacus", "Ramphastos toco", "Grus grus",
    "Fratercula arctica", "Larus argentatus", "Morus bassanus",
    "Diomedea exulans",

    # --- Reptiles and amphibians -------------------------------------------
    "Crocodylus niloticus", "Alligator mississippiensis", "Chelonia mydas",
    "Testudo hermanni", "Python regius", "Boa constrictor", "Naja naja",
    "Crotalus atrox", "Vipera berus", "Natrix natrix", "Varanus komodoensis",
    "Iguana iguana", "Chamaeleo chamaeleon", "Lacerta agilis",
    "Anguis fragilis", "Rana temporaria", "Bufo bufo",
    "Salamandra salamandra", "Triturus cristatus", "Dendrobates tinctorius",
    "Ambystoma mexicanum", "Xenopus laevis",

    # --- Fish ---------------------------------------------------------------
    "Carcharodon carcharias", "Rhincodon typus", "Manta birostris",
    "Salmo salar", "Salmo trutta", "Thunnus thynnus", "Gadus morhua",
    "Anguilla anguilla", "Hippocampus hippocampus", "Amphiprion ocellaris",
    "Carassius auratus", "Cyprinus carpio", "Esox lucius", "Perca fluviatilis",
    "Latimeria chalumnae",

    # --- Invertebrates ------------------------------------------------------
    "Bombus terrestris", "Danaus plexippus", "Vanessa atalanta",
    "Papilio machaon", "Coccinella septempunctata", "Lucanus cervus",
    "Formica rufa", "Araneus diadematus", "Octopus vulgaris",
    "Sepia officinalis", "Helix pomatia", "Homarus gammarus",
    "Cancer pagurus", "Carcinus maenas", "Asterias rubens", "Aurelia aurita",
    "Lumbricus terrestris",

    # --- Plants -------------------------------------------------------------
    "Quercus robur", "Fagus sylvatica", "Betula pendula", "Pinus sylvestris",
    "Picea abies", "Sequoiadendron giganteum", "Acer pseudoplatanus",
    "Fraxinus excelsior", "Salix alba", "Taxus baccata", "Ilex aquifolium",
    "Hedera helix", "Bellis perennis", "Taraxacum officinale",
    "Helianthus annuus", "Rosa canina", "Digitalis purpurea",
    "Primula vulgaris", "Papaver rhoeas", "Lavandula angustifolia",
    "Urtica dioica", "Triticum aestivum", "Zea mays", "Oryza sativa",
    "Solanum tuberosum", "Solanum lycopersicum", "Malus domestica",
    "Vitis vinifera", "Olea europaea", "Coffea arabica", "Theobroma cacao",
    "Musa acuminata", "Cocos nucifera", "Nymphaea alba", "Dionaea muscipula",

    # --- Fungi --------------------------------------------------------------
    "Agaricus bisporus", "Amanita muscaria", "Amanita phalloides",
    "Boletus edulis", "Cantharellus cibarius", "Pleurotus ostreatus",
    "Saccharomyces cerevisiae", "Penicillium chrysogenum",
    "Claviceps purpurea", "Coprinus comatus", "Ganoderma lucidum",
    "Tuber melanosporum", "Armillaria mellea", "Trichophyton rubrum",
]


class Command(BaseCommand):
    help = "Populate the database with a curated set of species from GBIF and Wikipedia"

    def add_arguments(self, parser):
        parser.add_argument(
            "--delay",
            type=float,
            default=1.0,
            help="Seconds to pause between species, to stay within API rate limits.",
        )
        parser.add_argument(
            "--file",
            type=str,
            help="Read names from a text file (one per line) instead of the built-in list.",
        )
        parser.add_argument(
            "--limit",
            type=int,
            help="Only process the first N names - handy for a quick trial run.",
        )

    def handle(self, *args, **options):
        names = self.get_names(options)
        total = len(names)
        created = skipped = failed = 0

        self.stdout.write(f"Seeding {total} species (delay {options['delay']}s)...")

        for index, name in enumerate(names, start=1):
            before = Taxon.objects.count()
            try:
                taxon = fetch_and_cache_taxon(name)
            except GBIFError as exc:
                # A network blip shouldn't abandon the rest of the batch.
                failed += 1
                self.stdout.write(self.style.ERROR(f"[{index}/{total}] {name}: {exc}"))
            else:
                if taxon is None:
                    failed += 1
                    self.stdout.write(self.style.WARNING(f"[{index}/{total}] {name}: no match"))
                elif Taxon.objects.count() > before:
                    created += 1
                    self.stdout.write(f"[{index}/{total}] {taxon.name}")
                else:
                    skipped += 1
                    self.stdout.write(f"[{index}/{total}] {taxon.name} (already cached)")

            # Be a good API citizen: space the requests out.
            if index < total:
                time.sleep(options["delay"])

        self.stdout.write(self.style.SUCCESS(
            f"Done. {created} added, {skipped} already cached, {failed} failed. "
            f"{Taxon.objects.count()} taxa in the database."
        ))

    def get_names(self, options):
        if options["file"]:
            with open(options["file"], encoding="utf-8") as handle:
                names = [line.strip() for line in handle if line.strip()]
        else:
            names = list(SPECIES)

        if options["limit"]:
            names = names[: options["limit"]]
        return names
